//
// mock.c - setuid program for launching mock.py
//
// 
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 2 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Library General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
//
// Copyright (c) 2006 - Clark Williams <williams@redhat.com>
//   portions lifted from mock-helper.c by Seth Vidal
//   namespace idea courtesy Enrico Scholz <enrico.scholz@informatik.tu-chemnitz.de>

//#define _GNU_SOURCE

#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <errno.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sched.h>
#include <assert.h>
#include <asm/unistd.h>
#include <signal.h>

#include "config.h"
#include "version.h"

#define PYTHON_PATH	"/usr/bin/python"
#define MOCK_PATH	"/usr/libexec/mock.py"

static char const * const ALLOWED_ENV[] =
{
	"dist",
	"ftp_proxy", 
	"http_proxy", 
	"https_proxy", 
	"no_proxy", 
	"PS1",
};

#define ALLOWED_ENV_SIZE (sizeof (ALLOWED_ENV) / sizeof (ALLOWED_ENV[0]))
#define SAFE_PATH	"PATH=/bin:/usr/bin:/usr/sbin"
#define SAFE_HOME	"HOME=/root"
#define NSFLAG		"NAMESPACE=1"

// Note that MAX_ENV_SIZE is allowed size, plus the ones we add plus a null entry
// so, if you add more variables, increase the constant below!
#define MAX_ENV_SIZE	4 + ALLOWED_ENV_SIZE

//
// helper functions
//

//
// print formatted string to stderr and terminate
//
void error (const char *format, ...)
{
	va_list ap;
	
	va_start (ap, format);
	fprintf (stderr, "mock: error: ");
	vfprintf (stderr, format, ap);
	va_end (ap);
	fprintf (stderr, "\n");
	exit (1);
}

//
// debug print
//
static int debugging = 0;

void debug(const char *format, ...)
{

	if (debugging) {
		va_list ap;
		
		va_start (ap, format);
		fprintf (stderr, "DEBUG: ");
		vfprintf (stderr, format, ap);
		va_end (ap);
	}
}

///////////////////////////////////////////
//
// main logic
//
//////////////////////////////////////////


int main (int argc, char **argv)
{
	char * env[MAX_ENV_SIZE+1] = {
		[0] = SAFE_PATH,
		[1] = SAFE_HOME,
		[2] = NSFLAG,
	};
	char **newargv;
	int newargc, newargvsz;
	int i, idx = 2;
	int status;
	pid_t pid;

	if (getenv("MOCKDEBUG"))
		debugging = 1;

	// copy in allowed environment variables to our environment
	debug("copying envionment\n");
	for (i = 0; i < ALLOWED_ENV_SIZE; ++i) {
		char *ptr = getenv (ALLOWED_ENV[i]);
		if (ptr==0) continue;
		ptr -= strlen (ALLOWED_ENV[i]) + 1;
		env[idx++] = ptr;
	}
	assert(idx <= MAX_ENV_SIZE);
	env[idx] = NULL;

	// set up a new argv/argc
	//     new argv[0] will be "/usr/bin/python"
	//     new argv[1] will be "/usr/libexec/mock.py"
	//     remainder of new argv will be old argv[1:n]
	//     allocate one extra for null at end
	newargc = argc + 1;
	newargvsz = sizeof(char *) * (newargc + 1);
	newargv = alloca(newargvsz);
	newargv[0] = PYTHON_PATH;
	debug("argv[0] = %s\n", newargv[0]);
	newargv[1] = MOCK_PATH;
	debug("argv[1] = %s\n", newargv[1]);
	for (i = 1; i < argc; i++) {
		newargv[i+1] = argv[i];
		debug("argv[%d] = %s\n", i+1, newargv[i+1]);
	}
	newargv[newargc] = NULL;

	// clone a new process with a separate namespace
	// Note: we have to use syscall here, since we want the
	//       raw system call 'clone', not the glibc library wrapper
	// Also note: The SIGCHLD or'ed into the flags argument. If you
	// don't specify an exit signal, the child is detached and waitpid
	// won't work (how the heck Enrico figured it out is beyond me, since
	// there are only two mentions of CSIGNAL in fork.c...)
	debug("cloning new namespace\n");
	pid = syscall(__NR_clone, CLONE_VFORK|CLONE_NEWNS|SIGCHLD, 0);

	// urk! no clone?
	if (pid == -1)
		error("clone failed: %s\n", strerror(errno));

	// exec python
	if (pid == 0) {
		debug("exec'ing python\n");
		execve(PYTHON_PATH, newargv, env);
		error("execve failed: %s\n", strerror(errno));
	}
	
	// wait for the child to finish and exit appropriately
	debug("waiting for child to finish\n");
	if (waitpid(pid, &status, 0) != pid)
		error("waitpid failed: %s\n", strerror(errno));
	if (WIFEXITED(status)) {
		debug("Exiting with status 0x%x (0x%x)\n", WEXITSTATUS(status), status);
		exit(WEXITSTATUS(status));
	}
	if (WIFSIGNALED(status))
		error("errored out with signal %d\n", WTERMSIG(status));

	exit(-1);	// WTF? how did we get here?
}
