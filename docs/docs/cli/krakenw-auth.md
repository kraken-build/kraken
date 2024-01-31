# `krakenw auth`

<!-- runcmd code: krakenw auth --help | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" -->
```
usage: krakenw auth [-h] [-u USERNAME] [-p PASSWORD] [--password-stdin] [-r] [-l] [-s] [--no-mask] [-v] [host]

Configure the credentials to use when accessing PyPI packages from the given host. The password will be stored in the system keychain.

positional arguments:
  host                              the host to add the credentials for

options:
  -h, --help                        show this help message and exit
  -u USERNAME, --username USERNAME  the username to use when accessing resources on the given host
  -p PASSWORD, --password PASSWORD  the password to use when accessing resources on the given host (use --password-stdin when possible)
  --password-stdin                  read the password from stdin
  -r, --remove                      remove credentials for the given host
  -l, --list                        list configured credentials for the given host
  -s, --no-check                    skip checking of auth credentials
  --no-mask                         do not mask credentials
  -v, --verbose                     show curl queries to use when authenicating hosts
```
<!-- end runcmd -->
