"""Run the production TLS lifecycle with real threads and injected key failures."""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile


def anchor_pattern(needle):
    """Regex for `needle`, tolerant of reformat spacing.

    These gates locate real source snippets by text and pin them. A
    clang-format pass must not be able to break that, so the pattern matches
    identifier/punctuation tokens separated by any whitespace, while the
    token sequence itself stays exact.
    """
    return r"\s*".join(
        re.escape(tok) for tok in re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", needle)
    )


def anchor(text, needle, start=0):
    """Index of `needle` in `text`, tolerant of reformat spacing."""
    match = re.search(anchor_pattern(needle), text[start:])
    if match is None:
        raise ValueError(f"anchor not found: {needle!r}")
    return start + match.start()


root = Path(__file__).resolve().parents[1]
source = (root / "src/ShadowCore.dylib/policy/EnvironmentPolicy.m").read_text()


def body(first, last):
    start = anchor(source, first)
    return source[start:anchor(source, last, start)]


storage = body("// Per-thread environment storage.", "// Shared PATH component filter")
storage += body("static void shdw_env_path_cache_invalidate(void)", "static int (*original_setenv)")
prefix = r'''
#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef bool BOOL;
#define NO false
#define YES true
static _Atomic int failure;
static _Atomic size_t allocated, freed, registrations;
static void *checked_malloc(size_t n) {
    void *p = malloc(n);
    if(p) allocated++;
    return p;
}
static void *checked_calloc(size_t n, size_t size) {
    if(failure == 3) return NULL;
    void *p = calloc(n, size);
    if(p) allocated++;
    return p;
}
static void checked_free(void *p) {
    if(p) freed++;
    free(p);
}
static int create_key(pthread_key_t *key, void (*destroy)(void *)) {
    if(failure == 1) return 11;
    return pthread_key_create(key, destroy);
}
static int set_key(pthread_key_t key, const void *value) {
    registrations++;
    if(failure == 2) return 12;
    return pthread_setspecific(key, value);
}
static void *get_key(pthread_key_t key) {
    assert(failure != 1);
    return pthread_getspecific(key);
}
#define free checked_free
#define malloc checked_malloc
#define calloc checked_calloc
#define pthread_key_create create_key
#define pthread_setspecific set_key
#define pthread_getspecific get_key
'''
suffix = r'''
enum { thread_count = 16 };
static pthread_mutex_t gate_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_condition = PTHREAD_COND_INITIALIZER;
static unsigned arrived;
static shdw_env_storage_t *records[thread_count];

static void *worker(void *argument) {
    uintptr_t index = (uintptr_t)argument;
    bool concurrent = index < thread_count;
    assert(!shdw_env_tls_get(NO));
    shdw_env_path_cache_invalidate(); // must not allocate an empty record
    assert(!shdw_env_tls_get(NO));
    if(failure) {
        assert(!shdw_env_tls_get(YES));
        assert(!shdw_env_tls_get(NO));
        if(failure == 1) return NULL;
        failure = 0; // allocation and registration failures are retryable
    }
    shdw_env_storage_t *storage = shdw_env_tls_get(YES);
    assert(storage);
    assert(shdw_env_tls_get(NO) == storage);
    assert(shdw_env_tls_get(YES) == storage);
    assert(!storage->path_storage && !storage->path_capacity);
    assert(!storage->path_cache_input && !storage->path_cache_capacity);
    assert(!storage->snapshot_filtered && !storage->snapshot_filtered_cap);
    assert(!storage->snapshot_path && !storage->snapshot_path_cap);
    assert(!storage->procargs_path && !storage->procargs_path_cap);
    storage->path_storage = malloc(8);
    storage->path_capacity = 8;
    storage->path_cache_input = malloc(8);
    storage->path_cache_capacity = 8;
    shdw_env_path_cache_invalidate();
    assert(!storage->path_cache_input && !storage->path_cache_capacity);
    assert(storage->path_storage && storage->path_capacity == 8);
    storage->path_cache_input = malloc(8);
    storage->snapshot_filtered = malloc(8);
    storage->snapshot_path = malloc(8);
    storage->procargs_path = malloc(8);
    assert(storage->path_storage && storage->path_cache_input);
    assert(storage->snapshot_filtered && storage->snapshot_path);
    assert(storage->procargs_path);
    memset(storage->path_storage, (int)index, 8);
    if(concurrent) {
        assert(pthread_mutex_lock(&gate_lock) == 0);
        records[index] = storage;
        if(++arrived == thread_count) {
            assert(pthread_cond_broadcast(&gate_condition) == 0);
        }
        while(arrived != thread_count) {
            assert(pthread_cond_wait(&gate_condition, &gate_lock) == 0);
        }
        for(unsigned i = 0; i < thread_count; i++) {
            assert(records[i]);
            if(i != index) assert(records[i] != storage);
        }
        assert(pthread_mutex_unlock(&gate_lock) == 0);
    }
    for(unsigned i = 0; i < 8; i++) {
        assert((unsigned char)storage->path_storage[i] == (unsigned char)index);
    }
    return NULL;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    int mode = atoi(argv[1]);
    failure = mode;
    pthread_t thread;
    assert(pthread_create(&thread, NULL, worker, (void *)(uintptr_t)thread_count) == 0);
    assert(pthread_join(thread, NULL) == 0);
    assert(allocated == freed);
    assert(allocated == (mode == 1 ? 0 : mode == 2 ? 8 : 7));
    assert(registrations == (mode == 1 ? 0 : mode == 2 ? 2 : 1));
    if(mode == 1) return 0;
    assert(!shdw_env_tls_get(NO)); // worker storage is isolated

    pthread_t threads[thread_count];
    for(uintptr_t i = 0; i < thread_count; i++) {
        assert(pthread_create(&threads[i], NULL, worker, (void *)i) == 0);
    }
    for(unsigned i = 0; i < thread_count; i++) {
        assert(pthread_join(threads[i], NULL) == 0);
    }
    assert(allocated == freed);
    assert(!shdw_env_tls_get(NO));

    for(unsigned i = 0; i < 32; i++) {
        assert(pthread_create(&thread, NULL, worker,
                              (void *)(uintptr_t)thread_count) == 0);
        assert(pthread_join(thread, NULL) == 0);
        assert(allocated == freed);
    }
    assert(registrations == (size_t)(mode == 2 ? 2 : 1) + thread_count + 32);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="shadow-env-storage-") as tmp:
    test = Path(tmp) / "test.c"
    binary = Path(tmp) / "test"
    test.write_text(prefix + storage + suffix)
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra",
                    "-Werror", "-pthread",
                    *shlex.split(os.environ.get("CFLAGS", "")),
                    str(test), "-o", str(binary)], check=True)
    for failure in range(4):
        subprocess.run([str(binary), str(failure)], check=True)

# Darwin integration: exercise the actual Foundation-facing functions as well
# as their storage owner. Only the path classifier is a synthetic test double.
if sys.platform == "darwin":
    integration = r'''
#import <Foundation/Foundation.h>
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
static _Atomic size_t allocated, freed;
static void *counted_calloc(size_t n, size_t size) {
    void *p = calloc(n, size);
    if(p) allocated++;
    return p;
}
static void *counted_realloc(void *p, size_t n) {
    bool new_allocation = p == NULL;
    void *result = realloc(p, n);
    if(result && new_allocation) allocated++;
    return result;
}
static void counted_free(void *p) { if(p) freed++; free(p); }
#define calloc counted_calloc
#define realloc counted_realloc
#define free counted_free
static BOOL shdw_is_restricted_root_c(const char *p) {
    return strncmp(p, "/excluded/", 10) == 0;
}
'''
    integration += body("static BOOL shdw_env_hidden(", "// Per-thread environment storage.")
    integration += storage
    integration += body("static NSString *shdw_env_filtered_path_string(", "#ifndef SHADOW_TEST_HARNESS")
    integration += body("char *shdw_env_sanitized_path_entry(", "NSDictionary *shdw_env_sanitized_dictionary(")
    integration += body("char ***shdw_env_filtered_snapshot(", "// KERN_PROCARGS2")
    integration += r'''
static void *api_worker(void *unused) {
    (void)unused;
    @autoreleasepool {
        assert(shdw_env_sanitized_path(NULL) == NULL);
        assert(shdw_env_filtered_snapshot(NULL) == NULL);
        assert(shdw_env_tls_get(NO) == NULL);
        const char *raw = "/usr/bin:/excluded/cache:/bin";
        char *value = shdw_env_sanitized_path(raw);
        assert(value && strcmp(value, "/usr/bin:/bin") == 0);
        assert(shdw_env_sanitized_path(raw) == value);
        char *entries[] = {"PATH=/bin:/excluded/cache", "TERM=test", NULL};
        char ***snapshot = shdw_env_filtered_snapshot(entries);
        assert(snapshot && *snapshot);
        assert(strcmp((*snapshot)[0], "PATH=/bin") == 0);
        assert(strcmp((*snapshot)[1], "TERM=test") == 0);
        assert((*snapshot)[2] == NULL);
        assert(strcmp(value, "/usr/bin:/bin") == 0);

        char longer[1024];
        memset(longer, 'a', sizeof(longer) - 1);
        longer[0] = '/';
        longer[sizeof(longer) - 1] = '\0';
        value = shdw_env_sanitized_path(longer);
        assert(value && strcmp(value, longer) == 0);
        assert(strcmp((*snapshot)[0], "PATH=/bin") == 0);
        char *more[] = {"PATH=/usr/local/bin:/excluded/cache:/bin", NULL};
        assert(shdw_env_filtered_snapshot(more) == snapshot);
        assert(strcmp((*snapshot)[0], "PATH=/usr/local/bin:/bin") == 0);
        assert((*snapshot)[1] == NULL);
        assert(strcmp(value, longer) == 0);
        shdw_env_path_cache_invalidate();
        assert(strcmp(value, longer) == 0);
        assert(strcmp((*snapshot)[0], "PATH=/usr/local/bin:/bin") == 0);
        assert(strcmp(shdw_env_sanitized_path(raw), "/usr/bin:/bin") == 0);
    }
    return NULL;
}
int main(void) {
    for(unsigned i = 0; i < 16; i++) {
        pthread_t thread;
        assert(pthread_create(&thread, NULL, api_worker, NULL) == 0);
        assert(pthread_join(thread, NULL) == 0);
        assert(allocated == freed);
    }
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="shadow-env-api-") as tmp:
        test = Path(tmp) / "test.m"
        binary = Path(tmp) / "test"
        test.write_text(integration)
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra",
                        "-Werror", "-pthread", "-fobjc-arc", "-framework", "Foundation",
                        *shlex.split(os.environ.get("CFLAGS", "")),
                        str(test), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

# Static ownership contract: capacity must be saved even when realloc stays put.
# The dictionary view must be driven by the shared name predicate: a hand-kept
# list drifts (it had already lost BOOTSTRAP_PREFIX, which getenv hid while
# NSProcessInfo.environment still returned it).
dict_fn = body("NSDictionary *shdw_env_sanitized_dictionary(", "// PATH: drop jailbreak components")
assert "shdw_env_name_hidden(" in dict_fn, (
    "shdw_env_sanitized_dictionary must use the shared name predicate")
assert 'hasPrefix:@"DYLD_"' not in dict_fn, (
    "the dictionary view must not keep a private env-key list")

procargs = source[anchor(source, "void shdw_procargs2_filter("):]
assert re.search(anchor_pattern(
    "e, &storage->procargs_path, &storage->procargs_path_cap"), procargs)
snapshot = body("char ***shdw_env_filtered_snapshot(", "// KERN_PROCARGS2")
assert re.search(anchor_pattern(
    "raw[i], &storage->snapshot_path, &storage->snapshot_path_cap"), snapshot)
assert "_Thread_local" not in storage
print("verify-environment-storage: thread cleanup, isolation, churn, setup failures, and capacity contract passed")
