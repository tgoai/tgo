# GeoIP Database Files

This directory contains ip2region xdb database files for IP geolocation lookup.

## Files

- `ip2region_v4.xdb` - IPv4 database (~11MB)
- `ip2region_v6.xdb` - IPv6 database (~35MB)

## Source

Downloaded from: https://github.com/lionsoul2014/ip2region

## Update

To update the database files, download the latest versions from:

```bash
cd resources/geoip

# IPv4
curl -L -o ip2region_v4.xdb "https://github.com/lionsoul2014/ip2region/raw/master/data/ip2region_v4.xdb"

# IPv6
curl -L -o ip2region_v6.xdb "https://github.com/lionsoul2014/ip2region/raw/master/data/ip2region_v6.xdb"
```

## Configuration

Set the following environment variables to use ip2region:

```bash
GEOIP_PROVIDER=ip2region
GEOIP_DATABASE_PATH=resources/geoip
GEOIP_ENABLED=true
```

## Note

These files are included in the repository for convenience. If you prefer not to include them in git, add this directory to `.gitignore`:

```
resources/geoip/*.xdb
```
