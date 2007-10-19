/* test program to test orhphanskill feature
 * compile it (per below) and put it in /tmp/ of the chroot.
 * Then: 
 *      mock -r CFG chroot /tmp/daemontest
 *
 * Expected output:
 *      INFO: mock suid wrapper version 0.8.0 
 *      INFO: mock.py version 0.8.0 starting...
 *      State Changed: start
 *      State Changed: init
 *      WARNING: Process ID 12180 still running in chroot. Killing...
 *
 */


/*
 * UNIX Daemon Server Programming Sample Program
 * Levent Karakas <levent at mektup dot at> May 2001
 *
 * To compile:  cc -o exampled examped.c
 * To run:      ./exampled
 * To test daemon:  ps -ef|grep exampled (or ps -aux on BSD systems)
 * To test log: tail -f /tmp/exampled.log
 * To test signal:  kill -HUP `cat /tmp/exampled.lock`
 * To terminate:    kill `cat /tmp/exampled.lock`
 * */

#include <stdio.h>
#include <fcntl.h>
#include <signal.h>
#include <unistd.h>

#define RUNNING_DIR "/tmp"
#define LOCK_FILE   "exampled.lock"
#define LOG_FILE    "exampled.log"

void log_message(filename,message)
char *filename;
char *message;
{
FILE *logfile;
    logfile=fopen(filename,"a");
    if(!logfile) return;
    fprintf(logfile,"%s\n",message);
    fclose(logfile);
}

void signal_handler(sig)
int sig;
{
    switch(sig) {
    case SIGHUP:
        log_message(LOG_FILE,"hangup signal catched");
        break;
    case SIGTERM:
        log_message(LOG_FILE,"terminate signal catched");
        exit(0);
        break;
    }
}

void daemonize()
{
int i,lfp;
char str[10];
    if(getppid()==1) return; /* already a daemon */
    i=fork();
    if (i<0) exit(1); /* fork error */
    if (i>0) exit(0); /* parent exits */
    /* child (daemon) continues */
    setsid(); /* obtain a new process group */
    for (i=getdtablesize();i>=0;--i) close(i); /* close all descriptors */
    i=open("/dev/null",O_RDWR); dup(i); dup(i); /* handle standart I/O */
    umask(027); /* set newly created file permissions */
    chdir(RUNNING_DIR); /* change running directory */
    lfp=open(LOCK_FILE,O_RDWR|O_CREAT,0640);
    if (lfp<0) exit(1); /* can not open */
    if (lockf(lfp,F_TLOCK,0)<0) exit(0); /* can not lock */
    /* first instance continues */
    sprintf(str,"%d\n",getpid());
    write(lfp,str,strlen(str)); /* record pid to lockfile */
    signal(SIGCHLD,SIG_IGN); /* ignore child */
    signal(SIGTSTP,SIG_IGN); /* ignore tty signals */
    signal(SIGTTOU,SIG_IGN);
    signal(SIGTTIN,SIG_IGN);
    signal(SIGHUP,signal_handler); /* catch hangup signal */
    signal(SIGTERM,signal_handler); /* catch kill signal */
}

main()
{
    daemonize();
    while(1) sleep(1); /* run */
}

/* EOF */
