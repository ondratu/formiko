/* Enchant provider for the Windows Spell Checking API - thread-safe variant.
 *
 * Modified copy of providers/enchant_winspell.cpp from Enchant
 * (https://github.com/rrthomas/enchant), same MIT licence as the original:
 *
 * MIT License
 *
 * Copyright (c) 2026 Moritz Mechelk
 *
 * HexChat
 * Copyright (c) 2015 Patrick Griffis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * Changes from upstream:
 *
 * - The upstream provider creates one apartment-threaded COM factory and
 *   spell checker on the thread that loads it and calls them from whatever
 *   thread Enchant is used on. Windows only allows that on the creating
 *   thread: from any other thread every check fails, which callers treat as
 *   "misspelled" (libspelling checks words on worker threads, so every word
 *   was underlined and no suggestions were offered). Here each thread
 *   initialises COM and creates its own factory and checkers on first use.
 * - The two tag conversions are done locally instead of via gnulib's bcp47.
 */

#include "config.h"

#include <glib.h>
#include <spellcheck.h>

#include "enchant-provider.h"

/* --------- Utils ----------*/

// "en_US" -> "en-US"; anything after '.' or '@' (encoding, modifier) is dropped
static char*
tag_xpg_to_bcp47(const char* const xpg)
{
	if (!xpg) {
		return nullptr;
	}

	char* bcp47 = g_strdup(xpg);
	for (char* p = bcp47; *p; p++) {
		if (*p == '.' || *p == '@') {
			*p = '\0';
			break;
		}
		if (*p == '_') {
			*p = '-';
		}
	}
	return bcp47;
}

// "en-US" -> "en_US"
static char*
tag_bcp47_to_xpg(const char* const bcp47)
{
	if (!bcp47) {
		return nullptr;
	}

	char* xpg = g_strdup(bcp47);
	for (char* p = xpg; *p; p++) {
		if (*p == '-') {
			*p = '_';
		}
	}
	return xpg;
}

static char**
enumstring_to_chararray(IEnumString* strings, size_t* out_len, gboolean tags_from_bcp47)
{
	GArray* array = g_array_new(TRUE, FALSE, sizeof(char*));

	LPOLESTR w_str;
	while (SUCCEEDED(strings->Next(1, &w_str, nullptr)) && w_str) {
		char* str = g_utf16_to_utf8((gunichar2*)w_str, -1, nullptr, nullptr, nullptr);

		if (str) {
			if (tags_from_bcp47) {
				char* xpg_tag = tag_bcp47_to_xpg(str);
				g_free(str);

				if (xpg_tag) {
					g_array_append_val(array, xpg_tag);
				}
			} else {
				g_array_append_val(array, str);
			}
		}

		CoTaskMemFree(w_str);
	}

	strings->Release();

	*out_len = array->len;
	return (char**)g_array_free(array, FALSE);
}

/* ---------- Per-thread COM state ------------ */

// COM objects are only used on the thread that created them, so each thread
// gets its own factory plus its own checker for every dictionary it touches.
struct ThreadState {
	bool com_initialized; // we must balance CoInitializeEx with CoUninitialize
	ISpellCheckerFactory* factory;
	GHashTable* checkers; // dictionary id -> ISpellChecker*
};

struct DictData {
	guint id; // key into ThreadState::checkers, never reused
	char* bcp47_tag;
};

static void
release_checker(gpointer checker)
{
	static_cast<ISpellChecker*>(checker)->Release();
}

static void
thread_state_free(gpointer data)
{
	auto state = static_cast<ThreadState*>(data);
	if (!state) {
		return;
	}

	g_hash_table_destroy(state->checkers);
	state->factory->Release();
	if (state->com_initialized) {
		CoUninitialize();
	}
	g_free(state);
}

static GPrivate thread_state_key = G_PRIVATE_INIT(thread_state_free);

static ThreadState*
get_thread_state()
{
	auto state = static_cast<ThreadState*>(g_private_get(&thread_state_key));
	if (state) {
		return state;
	}

	HRESULT hr = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
	// RPC_E_CHANGED_MODE: the thread already joined another apartment kind,
	// which is fine, COM is usable there too - it just is not ours to undo.
	if (FAILED(hr) && hr != RPC_E_CHANGED_MODE) {
		return nullptr;
	}
	bool com_initialized = SUCCEEDED(hr);

	ISpellCheckerFactory* factory = nullptr;
	if (FAILED(CoCreateInstance(__uuidof(SpellCheckerFactory), nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&factory)))) {
		if (com_initialized) {
			CoUninitialize();
		}
		return nullptr;
	}

	state = g_new0(ThreadState, 1);
	state->com_initialized = com_initialized;
	state->factory = factory;
	state->checkers = g_hash_table_new_full(g_direct_hash, g_direct_equal, nullptr, release_checker);
	g_private_set(&thread_state_key, state);
	return state;
}

// The checker for *data* on the calling thread, created on first use.
static ISpellChecker*
get_checker(DictData* data)
{
	ThreadState* state = get_thread_state();
	if (!state) {
		return nullptr;
	}

	gpointer key = GUINT_TO_POINTER(data->id);
	auto checker = static_cast<ISpellChecker*>(g_hash_table_lookup(state->checkers, key));
	if (checker) {
		return checker;
	}

	LPWSTR w_tag = (LPWSTR)g_utf8_to_utf16(data->bcp47_tag, -1, nullptr, nullptr, nullptr);
	if (!w_tag) {
		return nullptr;
	}
	HRESULT hr = state->factory->CreateSpellChecker(w_tag, &checker);
	g_free(w_tag);
	if (FAILED(hr)) {
		return nullptr;
	}

	g_hash_table_insert(state->checkers, key, checker);
	return checker;
}

/* ---------- Dict ------------ */

static void
winspell_dict_add_to_session(EnchantProviderDict* dict, const char* const word, size_t len)
{
	ISpellChecker* checker = get_checker(static_cast<DictData*>(dict->user_data));
	if (!checker) {
		return;
	}

	LPWSTR w_word = (LPWSTR)g_utf8_to_utf16(word, (glong)len, nullptr, nullptr, nullptr);

	if (w_word) {
		checker->Add(w_word);
		g_free(w_word);
	}
}

static void
winspell_dict_remove_from_session(EnchantProviderDict* dict, const char* const word, size_t len)
{
	ISpellChecker* checker = get_checker(static_cast<DictData*>(dict->user_data));
	if (!checker) {
		return;
	}

	// try to use ISpellChecker2::Remove if available (Windows 10+)
	ISpellChecker2* checker2;
	if (SUCCEEDED(checker->QueryInterface(__uuidof(ISpellChecker2), (void**)&checker2))) {
		LPWSTR w_word = (LPWSTR)g_utf8_to_utf16(word, (glong)len, nullptr, nullptr, nullptr);

		if (w_word) {
			checker2->Remove(w_word);
			g_free(w_word);
		}

		checker2->Release();
	}
}

static int
winspell_dict_check(EnchantProviderDict* dict, const char* const word, size_t len)
{
	ISpellChecker* checker = get_checker(static_cast<DictData*>(dict->user_data));
	if (!checker) {
		return -1; // error
	}

	LPWSTR w_word = (LPWSTR)g_utf8_to_utf16(word, (glong)len, nullptr, nullptr, nullptr);

	if (!w_word) {
		return -1; // conversion error
	}

	IEnumSpellingError* errors;
	HRESULT hr = checker->Check(w_word, &errors);
	g_free(w_word);

	if (FAILED(hr)) {
		return -1; // error
	}

	ISpellingError* error;
	if (errors->Next(&error) == S_OK) {
		error->Release();
		errors->Release();
		return 1; // spelling issue
	}

	errors->Release();
	return 0; // correct
}

static char**
winspell_dict_suggest(EnchantProviderDict* dict, const char* const word, size_t len, size_t* out_n_suggs)
{
	ISpellChecker* checker = get_checker(static_cast<DictData*>(dict->user_data));
	if (!checker) {
		*out_n_suggs = 0;
		return nullptr;
	}

	LPWSTR w_word = (LPWSTR)g_utf8_to_utf16(word, (glong)len, nullptr, nullptr, nullptr);

	if (!w_word) {
		*out_n_suggs = 0;
		return nullptr;
	}

	IEnumString* suggestions;
	HRESULT hr = checker->Suggest(w_word, &suggestions);
	g_free(w_word);

	if (FAILED(hr)) {
		*out_n_suggs = 0;
		return nullptr;
	}

	return enumstring_to_chararray(suggestions, out_n_suggs, FALSE);
}

/* ---------- Provider ------------ */

static EnchantProviderDict*
winspell_provider_request_dict(EnchantProvider* provider, const char* const xpg_tag)
{
	char* bcp47_tag = tag_xpg_to_bcp47(xpg_tag);
	if (!bcp47_tag) {
		return nullptr;
	}

	static gint next_id = 0;
	auto data = g_new0(DictData, 1);
	data->id = (guint)g_atomic_int_add(&next_id, 1) + 1;
	data->bcp47_tag = bcp47_tag;

	// Fail here, like upstream, if Windows has no checker for this language.
	if (!get_checker(data)) {
		g_free(data->bcp47_tag);
		g_free(data);
		return nullptr;
	}

	EnchantProviderDict* dict = enchant_provider_dict_new(provider, xpg_tag);
	dict->user_data = data;

	dict->suggest = winspell_dict_suggest;
	dict->check = winspell_dict_check;
	dict->add_to_session = winspell_dict_add_to_session;
	dict->remove_from_session = winspell_dict_remove_from_session;

	return dict;
}

static void
winspell_provider_dispose_dict(EnchantProvider*, EnchantProviderDict* dict)
{
	if (!dict) {
		return;
	}

	auto data = static_cast<DictData*>(dict->user_data);
	if (data) {
		// Only this thread's checker can be released from here; other
		// threads' entries go when those threads exit (ids are never reused).
		ThreadState* state = get_thread_state();
		if (state) {
			g_hash_table_remove(state->checkers, GUINT_TO_POINTER(data->id));
		}
		g_free(data->bcp47_tag);
		g_free(data);
	}
}

static int
winspell_provider_dictionary_exists(EnchantProvider*, const char* const xpg_tag)
{
	ThreadState* state = get_thread_state();
	if (!state) {
		return 0;
	}

	char* bcp47_tag = tag_xpg_to_bcp47(xpg_tag);
	if (!bcp47_tag) {
		return 0;
	}

	LPWSTR w_bcp47_tag = (LPWSTR)g_utf8_to_utf16(bcp47_tag, -1, nullptr, nullptr, nullptr);
	g_free(bcp47_tag);
	if (!w_bcp47_tag) {
		return 0;
	}

	BOOL is_supported = FALSE;
	state->factory->IsSupported(w_bcp47_tag, &is_supported);
	g_free(w_bcp47_tag);

	return is_supported;
}

static char**
winspell_provider_list_dicts(EnchantProvider*, size_t* out_n_dicts)
{
	ThreadState* state = get_thread_state();

	IEnumString* dicts;
	if (!state || FAILED(state->factory->get_SupportedLanguages(&dicts))) {
		*out_n_dicts = 0;
		return nullptr;
	}

	return enumstring_to_chararray(dicts, out_n_dicts, TRUE);
}

static void
winspell_provider_dispose(EnchantProvider*)
{
	// Per-thread state is released by each thread's GPrivate destructor.
}

static const char*
winspell_provider_identify(EnchantProvider*)
{
	return "winspell";
}

static const char*
winspell_provider_describe(EnchantProvider*)
{
	return "WinSpell Provider";
}

extern "C" EnchantProvider*
init_enchant_provider(void);

EnchantProvider*
init_enchant_provider(void)
{
	// Only proceed if the Windows spell checker is available at all.
	if (!get_thread_state()) {
		return nullptr;
	}

	EnchantProvider* provider = enchant_provider_new();

	provider->dispose = winspell_provider_dispose;
	provider->request_dict = winspell_provider_request_dict;
	provider->dispose_dict = winspell_provider_dispose_dict;
	provider->dictionary_exists = winspell_provider_dictionary_exists;
	provider->identify = winspell_provider_identify;
	provider->describe = winspell_provider_describe;
	provider->list_dicts = winspell_provider_list_dicts;

	return provider;
}
