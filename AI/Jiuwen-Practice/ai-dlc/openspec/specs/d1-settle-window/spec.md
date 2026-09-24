# d1-settle-window Specification

## Purpose
The mechanical check judges the settled filesystem, not a snapshot
raced against the session's last writes.

## Requirements

### Requirement: artifact checks run after writes settle

design-specify and design-pages-specify SHALL wait, before their
artifact existence checks, until every expected file exists and the
total size is stable across two consecutive probes, bounded by a
settle window; the window SHALL never fabricate a missing file —
after it closes the check decides on what is there.

#### Scenario: nominal

- **WHEN the session's round completes and the five artifacts land
  shortly after**
- **THEN the settle window SHALL outlast the late writes and the
  check SHALL report all_written true**

#### Scenario: never written

- **WHEN the files never land**
- **THEN the window SHALL close, the file SHALL not exist, and the
  check SHALL record the miss**
