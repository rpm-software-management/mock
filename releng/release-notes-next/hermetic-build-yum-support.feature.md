The ``--calculate-dependencies`` command now also supports the ``yum`` package
manager for building older distributions. Using the correct bootstrap image
with yum now works without problems. Also, ``mock-hermetic-repo`` was altered
to create repositories compatible with both ``dnf`` and ``yum`` package
managers (added ``--compatibility`` flag).
