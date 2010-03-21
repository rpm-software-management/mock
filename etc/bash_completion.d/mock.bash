# bash >= 3 completion for mock(1)

_mock()
{
    COMPREPLY=()

    local plugins="tmpfs root_cache yum_cache bind_mount ccache"
    local cfgdir=/etc/mock

    local word count=0
    for word in "${COMP_WORDS[@]}" ; do
        [ $count -eq $COMP_CWORD ] && break
        if [[ "$word" == --configdir ]] ; then
            cfgdir="${COMP_WORDS[((count+1))]}"
        elif [[ "$word" == --configdir=* ]] ; then
            cfgdir=${word/*=/}
        fi
        count=$((++count))
    done

    case "$3" in
        -h|--help|--copyin|--copyout|--arch|-D|--define|--with|--without|\
        --uniqueext|--rpmbuild_timeout|--sources|--cwd)
            return 0
            ;;
        -r|--root)
            COMPREPLY=( $( compgen -W "$( command ls $cfgdir 2>/dev/null | \
                sed -e '/^site-defaults\.cfg$/d' -ne 's/\.cfg$//p' )" \
                -- "$2" ) )
            return 0
            ;;
        --configdir|--resultdir)
            COMPREPLY=( $( compgen -d -- "$2" ) )
            return 0
            ;;
        --spec)
            COMPREPLY=( $( compgen -f -o plusdirs -X "!*.spec" -- "$2" ) )
            return 0
            ;;
        --target)
            # Yep, compatible archs, not compatible build archs
            # (e.g. ix86 chroot builds in x86_64 mock host)
            # This would actually depend on what the target root
            # can be used to build for...
            COMPREPLY=( $( compgen -W "$( command rpm --showrc | \
                sed -ne 's/^\s*compatible\s\s*archs\s*:\s*\(.*\)/\1/i p' )" \
                -- "$2" ) )
            return 0
            ;;
        --enable-plugin|--disable-plugin)
            COMPREPLY=( $( compgen -W "$plugins" -- "$2" ) )
            return 0
            ;;
    esac

    if [[ "$2" == -* ]] ; then
        COMPREPLY=( $( compgen -W "--version --help --rebuild --buildsrpm
            --shell --chroot --clean --init --installdeps --install --update
            --orphanskill --copyin --copyout --root --offline --no-clean
            --cleanup-after --no-cleanup-after --arch --target --define --with
            --without --resultdir --uniqueext --configdir --rpmbuild_timeout
            --unpriv --cwd --spec --sources --verbose --quiet --trace
            --enable-plugin --disable-plugin --print-root-path" -- "$2" ) )
        return 0
    fi

    COMPREPLY=( $( compgen -f -o plusdirs -X '!*.?(no)src.rpm' -- "$2" ) )
} &&
complete -F _mock -o filenames mock mock.py

# Local variables:
# mode: shell-script
# sh-basic-offset: 4
# sh-indent-comment: t
# indent-tabs-mode: nil
# End:
# ex: ts=4 sw=4 et filetype=sh
