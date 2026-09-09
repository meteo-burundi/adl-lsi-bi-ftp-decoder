---
adl_plugin:
  name: ADL LSI BI FTP Decoder
  connects_to: FTP decoder for LSI Lastem station exports
  category: country
  country: Burundi
  country_flag: "🇧🇮"
---
# ADL LSI BI FTP Decoder

Adds a **decoder** to the [ADL FTP Plugin](https://github.com/wmo-raf/adl-ftp-plugin)
for the tabular export files that the **LSI Lastem** data loggers of
Burundi's IGEBU (Institut Géographique du Burundi) write to an FTP server: a
two-row header (variable name, then statistic such as *Ave* or *Tot*), a
`Date/time` column, and the logger's own missing-value sentinels. With this
plugin installed, an ADL FTP/SFTP connection can select **LSI Decoder -
Burundi** as its decoder.

**Repository:** [adl-lsi-bi-ftp-decoder](https://github.com/meteo-burundi/adl-lsi-bi-ftp-decoder)
**Plugin type identifier:** `adl_lsi_bi_ftp_decoder` (defined but not registered — see below)
**Decoder identifier:** `lsi_burundi` · **Decoder display name:** *LSI Decoder - Burundi*
**Connection model:** none of its own — uses the FTP plugin's `NetworkFTP` · **Station link model:** the FTP plugin's `FTPStationLink`

> **Status of release 0.1.1.** The decoder in this release returns its records
> in a shape the FTP plugin does not accept, so **every file fails to decode**
> on ADL FTP Plugin 0.10.0 and later (see *Compatibility* and the first row of
> the feedback catalogue). This guide documents the file format and the
> configuration as designed, so that the fix is a plugin upgrade and not a
> reconfiguration. Do not expect observations from 0.1.1.

> **About the screenshots.** Every image in this guide is regenerated from
> `docs/screenshots.yml` against a seeded demo instance, so hostnames, station
> names, ids and readings in them are placeholders — not values to copy. The
> field tables are the reference for what to enter.

## Overview

This is a *decoder plugin*: it defines no connection or station link of its
own and never talks to a server. The FTP plugin does the listing and
downloading; this plugin turns each downloaded file into observation records.

```
LSI Lastem logger export ──▶ FTP server ──▶ ADL FTP Plugin (list, match, download)
                                                  │
                                                  ▼
                                   LSI Decoder - Burundi (this plugin)
                                                  │
                                                  ▼
                               records ──▶ variable mappings ──▶ ADL observations
```

The package ships a placeholder `Plugin` class (`adl_lsi_bi_ftp_decoder`) but
never registers it, so it does not appear in the *Add connection* plugin
chooser. The connection's plugin is *ADL FTP Plugin*; this plugin appears only
as an entry in that connection's **Decoder** list. Everything about hosts,
credentials, paths, listing strategies, downloads and the monitoring screens
is documented in the
[ADL FTP Plugin guide](https://github.com/wmo-raf/adl-ftp-plugin/blob/main/docs/guide.md);
this guide covers what is specific to the LSI files.

The decoder does not pass the file's column headers through as variable
names. It recognises the LSI header vocabulary (`AIRTemp`, `RELHumidity`,
`RAIN` …) and emits a fixed set of **canonical variable names** — those are
what you map, whatever the logger called its columns.

## Prerequisites

- A running ADL instance with the **ADL FTP Plugin** installed (this plugin
  imports from it and cannot load without it).
- FTP/SFTP access to the server the loggers export to — host, port, account,
  and the directory holding the files (see the FTP plugin guide's
  prerequisites for the network side).
- Files in the expected layout (next section). If the export configuration
  on the logger changes — extra statistics, renamed variables — the decoder's
  recognition table must change with it.

## Installation

Installed like any ADL plugin — see [Plugin Installation](https://adl-tool.readthedocs.io/en/latest/developer_guide/plugins/plugin_installation.html) for
all methods. Both entries are needed in `plugins.toml`, the FTP plugin first:

```toml
[[plugins]]
name = "ADL FTP Plugin"
git  = "https://github.com/wmo-raf/adl-ftp-plugin.git"
tag  = "0.13.0"

[[plugins]]
name = "ADL LSI BI FTP Decoder"
git  = "https://github.com/meteo-burundi/adl-lsi-bi-ftp-decoder.git"
tag  = "0.1.1"
```

After rebuild/restart, confirm both appear in `docker compose exec adl
list-plugins`, and that *LSI Decoder - Burundi* is offered in the Decoder list
of a new FTP connection.

## The file format this decoder reads

| Aspect | Expected |
|---|---|
| File name | Not constrained by the decoder — whatever the logger export writes. Match it with the station link's *File Pattern*. |
| Encoding / separators | Text, UTF-8. **Tab** or **comma** separated; the decoder picks whichever the first line contains more of. Blank lines are ignored. |
| Header row 1 | Variable names, one per column, e.g. `AIRTemp`, `RELHumidity`, `RAIN`, `WindDIR … RisDir`. |
| Header row 2 | The statistic of each column — `Ave`, `Inst`, `Min`, `Max`, `Tot`, `RisDir`, `Duration` … (`Avg` and `Instantaneous` are accepted spellings). |
| Timestamp column | Header matching `Date/time` (or `Datetime`), in ISO 8601 or `YYYY-MM-DD HH:MM:SS`. Rows whose timestamp does not parse are skipped. A file with no such column fails with `Timestamp column (Date/time) not found`. |
| Missing values | `-999999`, `-999999.00`, `-999990`, `-999990.00`, `-999.99`, `-999`, empty, `NA`, `NAN` (case-insensitive). Non-finite numbers are also treated as missing. |
| Rows | Everything from line 3 on. A row with no usable value in any recognised column is dropped. |
| Observation time | The `Date/time` value, read as the station's local time (the connection's *Stations Timezone*, or the station link's own). |

### Variables the decoder emits

The decoder matches header names case-insensitively against the patterns
below and keeps **one column per canonical name** — the first matching column
in file order, restricted to the preferred statistic where one is listed.

| Header pattern (row 1) | Statistic kept (row 2) | Canonical variable name (map this) | Typical unit |
|---|---|---|---|
| `BATTVoltage` | first found | `battery_voltage` | V |
| `INsideTEMP` | first found | `logger_box_temperature` | °C |
| `RELHumidity` | first found | `relative_humidity` | % |
| `AIRTemp` | first found | `air_temperature` | °C |
| `ATMPressure` | first found | `air_pressure` | hPa |
| `GLOBALRad` | first found | `global_radiation` | W/m² |
| `WindDIR` … `RisDir` | only `RisDir` (resultant direction) | `wind_direction` | degree |
| `WindSPEED` | first found | `wind_speed` | m/s |
| `RAIN` | only `Tot` | `precipitation_amount` | mm |
| `Temperature ('C) Msr.10` | first found | `soil_surface_temperature` | °C |
| `VolMoisture` | first found | `volumetric_soil_moisture` | % |
| `SOILTemp` | first found | `soil_temperature` | °C |
| `DirectRAD` | first found | `direct_radiation` | W/m² |
| `SUNShine` … `Duration` | `Duration` | `sunshine_duration` | per logger setting |

"First found" means that where a variable is exported with several
statistics (`Ave`, `Min`, `Max`, `Inst`), only the **leftmost** column is
kept. Order the export so the statistic you want comes first, or accept the
logger's default order. Columns matching no pattern are ignored.

## Connection configuration

Create a **Network FTP/SFTP** connection exactly as the FTP plugin guide
describes (connection type, host, port, username, password, passive mode,
timeout), then:

| Field | Value for this source |
|---|---|
| Decoder | **LSI Decoder - Burundi** |
| CSV Configuration | Leave empty — this decoder needs no configuration. |
| Variable Mappings | One row per canonical variable to store (below). Connection-level mappings apply to every station on the connection, which suits this source since the canonical names are the same for every logger. |

![FTP connection form with the decoder selected](images/lsi_bi_connection_form.png)

### Variable mappings

| Field | Description |
|---|---|
| ADL Parameter | The ADL `DataParameter` the values are stored under. |
| File Variable Name | The **canonical variable name** from the table above (e.g. `air_temperature`), not the header text in the file. |
| File Variable Unit | The unit the logger exports that variable in (check the logger's channel configuration). |

**Example:** ADL Parameter `Air Temperature` ← File Variable Name
`air_temperature`, unit `degC`; ADL Parameter `Precipitation` ← File Variable
Name `precipitation_amount`, unit `mm`.

![Connection-level variable mappings](images/lsi_bi_variable_mappings.png)

## Station link configuration

Create an **FTP/SFTP Station Link** per station (all fields are the FTP
plugin's; only the values matter here):

| Field | Value for this source |
|---|---|
| Remote Path | The directory the logger export writes into. |
| File Pattern | A glob selecting one station's files, e.g. `Bujumbura_*.csv`. |
| Directory Structured by Date | Off, unless the export nests directories by year/month/day on your server. |
| File Listing Strategy | **Pattern Only** if the directory is small; **Filter by Date** with the matching *Filename Date Format* if the export puts a date in the file name. This decoder does no date narrowing of its own. |
| Collection Start Date | Rows older than this are rejected by ADL even when the file is fetched. Set it for a backfill. |
| Skip downloading already downloaded files | **Off** if the logger appends to a running file (the usual LSI export), so the growing file is re-downloaded each run; on if each file is written once. |

![Station link form](images/lsi_bi_station_link_form.png)

## Admin UI added by this plugin

None. This plugin adds no page, menu entry, button or form of its own; the
only place it appears is as an option in the FTP connection's *Decoder*
select. The FTP plugin's own surfaces — *Test Decoder Configuration*, the
*Direct Fetch Files* preview, the *FTP station data files* list — work with
this decoder and are documented in the FTP plugin guide.

## Data collection behavior

One run, per enabled station link:

1. The FTP plugin lists *Remote Path* and keeps the names matching *File
   Pattern* (narrowed by file-name date under *Filter by Date*).
2. Each file not yet held (or every file, with *Skip downloading already
   downloaded files* off) is downloaded and handed to this decoder.
3. The decoder detects the delimiter, merges the two header rows, finds the
   `Date/time` column, maps each recognised column to its canonical name, and
   yields one record per data row that carries at least one value.
4. ADL applies the variable mappings and unit conversion and stores the
   values; rows already stored are updated, not duplicated.

- **Timezones:** file times are local station time; the station's timezone
  (connection default or per-link) is what ADL stamps them with.
- **Backfill:** set *Collection Start Date* before the first run.

## Source checks / diagnostics

All monitoring for a connection using this decoder is the FTP plugin's: the
**Ingestion Diagnostic** page proves the FTP host, port and account, and the
station link's **Station Source Check** proves the resolved remote path and
counts the files matching the pattern. How to read both screens is covered in
[Monitoring & Diagnostics](https://adl-tool.readthedocs.io/en/latest/user_guide/monitoring_and_diagnostics.html);
their FTP-specific messages are catalogued in the FTP plugin guide. This
plugin adds no check of its own — a file that lists and downloads fine but
does not decode shows up as an **error in the task log** and an unprocessed
row in the *FTP station data files* list, not in the source checks.

![Ingestion Diagnostic page for the FTP connection](images/lsi_bi_ingestion_diagnostic.png)

![Station Source Check on the station link](images/lsi_bi_station_source_check.png)

![FTP station data files list](images/lsi_bi_data_files.png)

### Feedback catalogue — messages involving this decoder

These appear in the station's activity log message or the run's task log
(Monitoring → the connection's activity):

| Message (example) | Where | Meaning | What to do |
|---|---|---|---|
| `Error decoding file Bujumbura_2025.csv: 'list' object has no attribute 'get'` | task log (error), every file | **Release 0.1.1 defect.** The decoder returns a plain list where the FTP plugin expects `{"values": [...]}`, so the pipeline cannot read its output. The same error appears in *Test Decoder Configuration*. | Nothing in the configuration fixes it; upgrade to a release whose changelog says the record shape was corrected. |
| `Error decoding file …: Timestamp column (Date/time) not found` | task log (error) | No header cell matches `Date/time`. | Open the file: check the first header row, the delimiter, and that the file is not a different export. |
| `Error decoding file …: [Errno 2] No such file or directory` | task log (error) | The staged file vanished between download and decode. | Transient; the next run re-fetches. |
| `File … decoded 0 record(s) but none of its values were saved — check the variable mappings and the ingestion window` | task log (warning) | The file had fewer than three non-blank lines, no timestamps parsed, or every row was empty in every recognised column. | Open the file; check the header vocabulary against the table above. |
| `File … decoded 144 record(s) but none of its values were saved — …` | task log (warning) | Rows decoded, but the mapping names do not match the canonical names, or every row lies before *Collection Start Date*. | Map the canonical names, not the file's headers; check the start date. |
| `Resolved remote path /export: 0 file(s) matching 'Bujumbura_*.csv'.` | Station Source Check (OK) | The FTP plugin's station check: path found, nothing matches right now. | Check the pattern and that the export has run. |

## Troubleshooting

**Every file fails with `'list' object has no attribute 'get'`**
: Release 0.1.1 — see the status note at the top. Upgrade when a fixed
  release is published.

**Files decode but *values saved* is 0**
: The mappings use the file's header text (`AIRTemp`) instead of the canonical
  name (`air_temperature`). Use *Test Decoder Configuration* on the connection
  to see the exact keys the decoder emits.

**Rainfall is missing although the file has a `RAIN` column**
: Only the `Tot` statistic of `RAIN` is kept. If the export writes `RAIN`
  with `Inst` or `Ave` only, reconfigure the export to include the total.

**Wind direction is missing**
: Only the `RisDir` (resultant direction) statistic of `WindDIR` is kept.

**Only the first of several `AIRTemp` columns is stored**
: By design — one column per canonical name. Reorder the export if you need
  a different statistic.

## Compatibility

| Plugin version | Requires | Notes |
|---|---|---|
| 0.1.1 | ADL FTP Plugin (imports its decoder registry), ADL core 0.8.x | Current release. **Does not produce observations**: `decode()` returns a list of `{observation_time, values}` entries with an ISO-string time, while the FTP plugin's pipeline (0.10.0 and later, and the *Test Decoder Configuration* view) reads `result.get("values")` and expects flat records with a `datetime` — every file raises `'list' object has no attribute 'get'`. |

## Changelog

See [GitHub Releases](https://github.com/meteo-burundi/adl-lsi-bi-ftp-decoder/releases).
