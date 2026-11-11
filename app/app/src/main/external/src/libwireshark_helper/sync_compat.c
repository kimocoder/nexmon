/* glib in prebuildlibs/ was compiled for ARMv5TE, which has no ldrex/strex, so
 * its atomic operations are out-of-line calls to GCC's __sync_* helpers.
 * Compiler-rt on Android does not provide those, and the objects cannot be
 * recompiled, so supply the two that glib references. They are only reached
 * through glib's own atomics.
 *
 * clang treats __sync_* as builtins, so the functions carry an asm label
 * instead of the builtin name. */
#include <stdint.h>

void sync_synchronize(void) __asm__("__sync_synchronize");
void sync_synchronize(void)
{
	__atomic_thread_fence(__ATOMIC_SEQ_CST);
}

uint32_t sync_val_compare_and_swap_4(void *, uint32_t, uint32_t)
	__asm__("__sync_val_compare_and_swap_4");
uint32_t sync_val_compare_and_swap_4(void *ptr, uint32_t oldval, uint32_t newval)
{
	uint32_t expected = oldval;
	__atomic_compare_exchange_n((uint32_t *)ptr, &expected, newval, 0,
	                            __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
	return expected;
}