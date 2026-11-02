import sys
from pathlib import Path

import pytest
from sqlalchemy import (
    Column, ForeignKey, Integer, MetaData, String, Table,
    create_engine, event, func, insert, select,
)
from sqlalchemy.exc import IntegrityError

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from DatabaseMigration.databaseMigrationUtility import DatabaseDeletionHelper


@pytest.fixture
def database_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    metadata = MetaData()
    locations = Table("ref_dataLocation", metadata, Column("code", String(25), primary_key=True))
    sources = Table("ref_dataSource", metadata, Column("code", String(25), primary_key=True))
    inputs = Table(
        "inputs", metadata,
        Column("id", Integer, primary_key=True),
        Column("dataLocation", String(25), ForeignKey("ref_dataLocation.code")),
    )
    mapping = Table(
        "dataLocation_dataSource_mapping", metadata,
        Column("id", Integer, primary_key=True),
        Column("dataLocationCode", String(25), ForeignKey("ref_dataLocation.code")),
        Column("dataSourceCode", String(25), ForeignKey("ref_dataSource.code")),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(insert(locations).values(code="test-location"))
        connection.execute(insert(sources).values(code="test-source"))
        connection.execute(insert(sources).values(code="other-source"))
        connection.execute(insert(inputs).values(dataLocation="test-location"))
        connection.execute(insert(mapping).values(
            dataLocationCode="test-location", dataSourceCode="test-source"
        ))
        connection.execute(insert(mapping).values(
            dataLocationCode="test-location", dataSourceCode="other-source"
        ))

    yield engine
    engine.dispose()


def _count_rows(connection, table_name):
    table = Table(table_name, MetaData(), autoload_with=connection)
    return connection.execute(select(func.count()).select_from(table)).scalar_one()


def test_helper_requires_an_active_transaction(database_engine):
    with database_engine.connect() as connection:
        with pytest.raises(RuntimeError, match="active transaction"):
            DatabaseDeletionHelper(connection)


def test_failed_reference_delete_rolls_back_prior_mapping_deletion(
    database_engine, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(IntegrityError):
        with database_engine.begin() as connection:
            helper = DatabaseDeletionHelper(connection)
            helper.delete_mapping_row("test-location", "test-source")
            helper.delete_reference_row("ref_dataSource", "test-source")
            # Existing input and another mapping still reference this location.
            helper.delete_reference_row("ref_dataLocation", "test-location")

    with database_engine.connect() as connection:
        assert _count_rows(connection, "inputs") == 1
        assert _count_rows(connection, "dataLocation_dataSource_mapping") == 2
        assert _count_rows(connection, "ref_dataLocation") == 1
        assert _count_rows(connection, "ref_dataSource") == 2
    assert not (tmp_path / "deletion_dump.txt").exists()


def test_mapping_delete_removes_only_the_exact_location_source_pair(
    database_engine, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    with database_engine.begin() as connection:
        helper = DatabaseDeletionHelper(connection)
        helper.delete_mapping_row("test-location", "test-source")
    helper.write_deletion_dump()

    with database_engine.connect() as connection:
        assert _count_rows(connection, "dataLocation_dataSource_mapping") == 1
        assert _count_rows(connection, "inputs") == 1
        assert _count_rows(connection, "ref_dataLocation") == 1
        assert _count_rows(connection, "ref_dataSource") == 2
    dump_lines = (tmp_path / "deletion_dump.txt").read_text(encoding="utf-8").splitlines()
    assert len(dump_lines) == 1


def test_deletion_dump_is_written_only_after_successful_commit(
    database_engine, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    with database_engine.begin() as connection:
        helper = DatabaseDeletionHelper(connection)
        helper.delete_mapping_row("test-location", "test-source")
        with pytest.raises(RuntimeError, match="after the migration transaction commits"):
            helper.write_deletion_dump()
    helper.write_deletion_dump()
    assert (tmp_path / "deletion_dump.txt").exists()


def test_deletion_dump_failure_does_not_undo_a_committed_migration(
    database_engine, monkeypatch
):
    with database_engine.begin() as connection:
        helper = DatabaseDeletionHelper(connection)
        helper.delete_mapping_row("test-location", "test-source")

    def fail_open(*args, **kwargs):
        raise OSError("disk is unavailable")

    monkeypatch.setattr("builtins.open", fail_open)
    helper.write_deletion_dump()
    with database_engine.connect() as connection:
        assert _count_rows(connection, "dataLocation_dataSource_mapping") == 1
