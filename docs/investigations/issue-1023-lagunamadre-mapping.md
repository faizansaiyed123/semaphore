# Issue #1023: Laguna Madre TCOON mapping investigation

**Status:** Investigation complete; production cleanup decision requires maintainer confirmation.  
**Scope:** Explain why `lagunamadre | tcoon` exists in some databases but not in a fresh local database, determine whether the current repository uses TCOON, and recommend a safe resolution.

## Findings

### 1. The environment difference is explained by migration history

The original version 1.0 seed file, `tools/DatabaseMigration/1_0/init_data/dataMapping.csv`, contained:

```csv
lagunamadre,tcoon,48646513645,0
```

Commit [0f78ea0](https://github.com/conrad-blucher-institute/semaphore/commit/0f78ea0c5b37c412e3006a6bf243fe6d914de058) changed that seed mapping from `tcoon` to `LIGHTHOUSE`.

Migration [2.12](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/2_12/2_12_DatabaseMigration.py) removes the `lagunamadre + LIGHTHOUSE` mapping. It does not remove the earlier `lagunamadre + tcoon` row.

This gives a consistent explanation for the reported difference:

- A database initialized before the seed change can retain the TCOON row. Editing a seed CSV does not update rows already stored in an existing database.
- A fresh database reads the changed version 1.0 seed (LIGHTHOUSE) and later runs migration 2.12, which removes that mapping. It therefore ends without either the old TCOON row or the LIGHTHOUSE row.

Migration [2.9](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/2_9/2_9_DatabaseMigration.py) separately adds `lagunamadre | NDFD_EXP | 0 | 0`. That mapping is unrelated to the missing TCOON row.

### 2. The current checked-in application does not implement TCOON ingestion

The current `src/semaphore/DataIngestion/DI_Classes` directory contains source classes such as `LIGHTHOUSE.py`, `NOAATANDC.py`, `NDFD.py`, and `NDFD_EXP.py`. It does not contain a TCOON/tcoon ingestion class.

The [data ingestion factory](https://github.com/conrad-blucher-institute/semaphore/blob/main/src/semaphore/DataIngestion/IDataIngestion.py) dynamically imports `DI_Classes.<dataSource>`. A request configured with `dataSource = "tcoon"` therefore cannot be handled by the checked-in ingestion classes and raises `ModuleNotFoundError`.

A repository-wide search for TCOON finds the legacy `tcoon` reference-data entry in `tools/DatabaseMigration/1_0/init_data/dataSource.csv` and a historical Magnolia station description. It does not show current TCOON ingestion or DSPEC usage.

**Boundary of this finding:** Repository inspection cannot rule out external DSPECs, deployment configuration, database consumers, or workflows that are not stored in this repository. The existence of the `tcoon` reference-data entry alone does not prove an active dependency.

### 3. Avoid broad deletion when cleaning up the row

The current `DatabaseDeletionHelper.delete_mapping_row()` filters only by `dataLocationCode` and `dataSourceCode`. The mapping table's unique key also includes `dataSourceLocationCode` and `priorityOrder`. Reusing that helper for this cleanup could remove more than the one intended row if multiple mappings exist for the same location and source.

See [databaseMigrationUtility.py](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/databaseMigrationUtility.py).

## Recommendation

1. **Do not restore TCOON to the fresh-database seed.** The current repository has no TCOON ingestion implementation to consume it.
2. **Do not delete the production/development row yet.** First ask the maintainers or deployment owners to confirm that no external DSPEC, service, or operational workflow still requests `tcoon`.
3. **If there are no external consumers, remove only the exact legacy mapping** `(lagunamadre, tcoon, 48646513645, 0)` with a small forward migration. The deletion predicate should include all four values (or the row's primary key), and the migration should be safe when the row is already absent.
4. **Test both upgrade and rollback** against a database containing the row and one without it. Confirm that no other mapping rows are changed.

No migration or runtime-code change is proposed in this investigation. The only unresolved decision is the external dependency check before any existing dev/prod row is removed.

## Relevant repository history

- [Original/changed version 1.0 mapping seed](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/1_0/init_data/dataMapping.csv)
- [Commit changing TCOON to LIGHTHOUSE](https://github.com/conrad-blucher-institute/semaphore/commit/0f78ea0c5b37c412e3006a6bf243fe6d914de058)
- [Migration 2.9: separate NDFD_EXP mapping](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/2_9/2_9_DatabaseMigration.py)
- [Migration 2.12: remove LIGHTHOUSE mapping](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/2_12/2_12_DatabaseMigration.py)
- [Current data ingestion factory](https://github.com/conrad-blucher-institute/semaphore/blob/main/src/semaphore/DataIngestion/IDataIngestion.py)
- [Mapping deletion helper](https://github.com/conrad-blucher-institute/semaphore/blob/main/tools/DatabaseMigration/databaseMigrationUtility.py)
