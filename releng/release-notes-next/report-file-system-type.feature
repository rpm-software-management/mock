Previously, only the file sizes were reported by the hw_info plugin:

~~~
Filesystem                                             Size  Used Avail Use% Mounted on
/dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  399G  9.1G  373G   3% /
/dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  399G  9.1G  373G   3% /
~~~

Newly, [also file system type is reported][issue#1263]:

~~~
Filesystem                                             Type   Size  Used Avail Use% Mounted on
/dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  btrfs  399G  9.1G  373G   3% /
/dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  btrfs  399G  9.1G  373G   3% /
~~~
