FROM registry.fedoraproject.org/fedora:rawhide

RUN dnf -y install fedpkg tito argparse-manpage bash-completion python3-devel python3-jsonschema python3-pytest
RUN useradd -m -G mock -u 1001 user
WORKDIR /home/user

COPY mock/ /home/user/mock
RUN chown -R user:user /home/user/mock
USER user
WORKDIR /home/user/mock/mock-core-configs
RUN tito build --test --rpm
WORKDIR /home/user/mock/mock
RUN tito build --test --rpm
USER root
RUN dnf -y copr enable @mock/mock-deps
RUN dnf -y install --allow-downgrade /tmp/tito/*/mock*.rpm
USER user
