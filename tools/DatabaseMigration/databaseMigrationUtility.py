# -*- coding: utf-8 -*-
# databaseMigrationUtility.py
# ----------------------------------
"""Utilities for explicit, transactional database migration deletions."""

from sqlalchemy import Connection, MetaData, delete


class DatabaseDeletionHelper:
    """Delete migration-owned reference rows on a caller-managed connection.

    The caller must create this helper inside ``with engine.begin()``. The
    helper never opens a connection or commits. It deliberately does not
    delete dependent inputs/outputs: foreign-key constraints prevent a
    rollback from destroying data created after the original migration.
    """

    def __init__(self, connection: Connection):
        if not connection.in_transaction():
            raise RuntimeError(
                "DatabaseDeletionHelper requires an active transaction; "
                "pass a connection from 'with databaseEngine.begin()'."
            )
        self.__connection = connection
        self.__metadata = MetaData()
        self.__metadata.reflect(bind=connection)
        self.__deleted_rows = []

    def __require_active_transaction(self) -> None:
        if not self.__connection.in_transaction():
            raise RuntimeError(
                "The migration transaction is no longer active. "
                "Create the helper inside 'with databaseEngine.begin()'."
            )

    def __record_deleted_rows(self, result) -> None:
        self.__deleted_rows.extend(result.fetchall())

    def delete_reference_row(self, table_name: str, keyword: str) -> None:
        """Delete a migration-owned row from an explicitly named reference table."""
        self.__require_active_transaction()
        if not table_name.startswith("ref_"):
            raise ValueError(f"Expected a reference table, got {table_name!r}")
        table = self.__metadata.tables[table_name]
        result = self.__connection.execute(
            delete(table).where(table.c.code == keyword).returning(table)
        )
        self.__record_deleted_rows(result)

    def delete_mapping_row(self, dataLocationCode: str, dataSourceCode: str) -> None:
        """Delete only the exact location/source mapping owned by a migration."""
        self.__require_active_transaction()
        table = self.__metadata.tables["dataLocation_dataSource_mapping"]
        result = self.__connection.execute(
            delete(table)
            .where(
                (table.c.dataLocationCode == dataLocationCode)
                & (table.c.dataSourceCode == dataSourceCode)
            )
            .returning(table)
        )
        self.__record_deleted_rows(result)

    def write_deletion_dump(self) -> None:
        """Persist deleted rows after commit; dump failure must not undo the DB migration."""
        if self.__connection.in_transaction():
            raise RuntimeError(
                "Write the deletion dump only after the migration transaction commits."
            )
        if not self.__deleted_rows:
            return
        try:
            with open("deletion_dump.txt", "a", encoding="utf-8") as file:
                for row in self.__deleted_rows:
                    file.write(f"{row}\n")
        except OSError as error:
            # The database transaction is already committed. A diagnostic dump
            # failure must not cause migrate_db.py to skip its version update.
            print(f"Warning: failed to write deletion dump: {error}")
        finally:
            self.__deleted_rows.clear()
