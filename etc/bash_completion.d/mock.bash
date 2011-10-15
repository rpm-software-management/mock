# bash >= 3 completion for mock(1)

_mock()
{
    COMPREPLY=()
    local cur prev cword cfgdir=/etc/mock
    local -a words
    if declare -F _get_comp_words_by_ref &>/dev/null ; then
        _get_comp_words_by_ref cur prev words cword
    else
        cur=$2 prev=$3 words=("${COMP_WORDS[@]}") cword=$COMP_CWORD
    fi

    local word count=0
    for word in "${words[@]}" ; do
        [[ $count -eq $cword ]] && break
        if [[ "$word" == --configdir ]] ; then
            cfgdir="${words[((count+1))]}"
        elif [[ "$word" == --configdir=* ]] ; then
            cfgdir=${word/*=/}
        fi
        count=$((++count))
    done

    local split=false
    declare -F _split_longopt &>/dev/null && _split_longopt && split=true

    case "$prev" in
        -h|--help|--copyin|--copyout|--arch|-D|--define|--with|--without|\
        --uniqueext|--rpmbuild_timeout|--sources|--cwd|--scm-option)
            return 0
            ;;
        -r|--root)
            COMPREPLY=( $( compgen -W "$( command ls $cfgdir 2>/dev/null | \
                sed -ne 's/\.cfg$//p' )" -X site-defaults -- "$cur" ) )
            return 0
            ;;
        --configdir|--resultdir)
            COMPREPLY=( $( compgen -d -- "$cur" ) )
            return 0
            ;;
        --spec)
            COMPREPLY=( $( compgen -f -o plusdirs -X "!*.spec" -- "$cur" ) )
            return 0
            ;;
        --target)
            # Yep, compatible archs, not compatible build archs
            # (e.g. ix86 chroot builds in x86_64 mock host)
            # This would actually depend on what the target root
            # can be used to build for...
            COMPREPLY=( $( compgen -W "$( command rpm --showrc | \
                sed -ne 's/^\s*compatible\s\s*archs\s*:\s*\(.*\)/\1/i p' )" \
                -- "$cur" ) )
            return 0
            ;;
        --enable-plugin|--disable-plugin)
            COMPREPLY=( $( compgen -W "$( $1 $prev=DOES_NOT_EXIST 2>&1 | \
                sed -ne "s/[',]//g" -e 's/.*[[(]\([^])]*\)[])]/\1/p' )" \
                -- "$cur" ) ) #' unconfuse emacs
            return 0
            ;;
        --scrub)
            COMPREPLY=( $( compgen -W "all chroot cache root-cache c-cache
                yum-cache" -- "$cur" ) )
            return 0
            ;;
        --install|install)
            COMPREPLY=( $( compgen -f -o plusdirs -X '!*.rpm' -X '*src.rpm' \
                -- "$cur" ) )
            [[ $cur != */* && $cur != [.~]* ]] && \
                declare -F _yum_list &>/dev/null && _yum_list all "$cur"
            return 0
            ;;
    esac

    $split && return 0

    if [[ "$cur" == -* ]] ; then
        COMPREPLY=( $( compgen -W "--version --help --rebuild --buildsrpm
            --shell --chroot --clean --scrub --init --installdeps --install
            --update --orphanskill --copyin --copyout --root --offline
            --no-clean --cleanup-after --no-cleanup-after --arch --target
            --define --with --without --resultdir --uniqueext --configdir
            --rpmbuild_timeout --unpriv --cwd --spec --sources --verbose
            --quiet --trace --enable-plugin --disable-plugin
            --print-root-path --scm-enable --scm-option" -- "$cur" ) )
        return 0
    fi

    COMPREPLY=( $( compgen -f -o plusdirs -X '!*.@(?(no)src.r|s)pm' \
        -- "$cur" ) )
} &&
complete -F _mock -o filenames mock mock.py

# Local variables:
# mode: shell-script
# sh-basic-offset: 4
# sh-indent-comment: t
# indent-tabs-mode: nil
# End:
# ex: ts=4 sw=4 et filetype=sh
