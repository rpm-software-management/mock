#include <selinux/selinux.h>

extern int is_selinux_enabled(void)
{
  /* always return 0; this way we don't trigger any SELINUX calls */
  return 0;
}

/* this function gives failures when installing basic rpms in the root;
 * so we fake it out as well */
extern int lsetfilecon(const char *path, security_context_t con)
{
  return 0;
}
