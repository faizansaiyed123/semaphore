# -*- coding: utf-8 -*-
# 3_8_DatabaseMigration.py
# ----------------------------------
# Created By: CJ Quintero
# Created Date: 08/31/2026
# Version 1.0
# ----------------------------------
"""
This db migration script adds Seadrift, Aransas Wildlife Refuge, and ESB to the ref_dataLocation table
and adds Port Lavaca, Seadrift, and Aransas Wildlife Refuge to the dataLocation_dataSource_mapping table
for the operation of the ESB cold stunning model.

NOTE: The location and mapping CSV files do not contain the same rows.
Rollback removes only the mapping pairs and reference locations introduced by
this migration. It intentionally preserves input/output data created after the
migration; foreign-key constraints prevent removing a location that is still
referenced.
""" 
# ----------------------------------
# 
#
# Imports
from DatabaseMigration.IDatabaseMigration import IDatabaseMigration
from DatabaseMigration.databaseMigrationUtility import DatabaseDeletionHelper
from sqlalchemy import Engine
from sqlalchemy.sql import text
import csv

# Constants
MAPPING_CSV = './tools/DatabaseMigration/3_8/init_data/dataMapping.csv'
LOCATION_CSV = './tools/DatabaseMigration/3_8/init_data/dataLocation.csv'


class Migrator(IDatabaseMigration):

    def update(self, databaseEngine: Engine) -> bool:
        """
        This function updates the database to version 3.8 which adds rows to the
        dataLocation_dataSource_mapping table and the ref_dataLocation table.
        The rows added are read from the dataLocation.csv and dataMapping.csv files.

        :param databaseEngine: Engine - the engine of the database we are connecting to (semaphore)

        :return: bool indicating successful update

        NOTE: Both tables use strings as the data type for all values except for priorityOrder which
        is an integer.
        """
        # read the rows 
        location_rows, mapping_rows = self._read_rows()

        with databaseEngine.connect() as conn:
            # conn.begin() will commit a single transaction at the end of the with block
            with conn.begin():

                # this creates many VALUES clauses to insert all rows in a single statement such as:
                # (:code0, :displayName0, :notes0, :latitude0, :longitude0),
                # (:code1, :displayName1, :notes1, :latitude1, :longitude1), ...
                values_clause = ", ".join(
                    f"(:code{i}, :displayName{i}, :notes{i}, :latitude{i}, :longitude{i})"
                    for i in range(len(location_rows))
                )

                stmt = text(f"""
                INSERT INTO "ref_dataLocation" (
                    "code",
                    "displayName",
                    "notes",
                    "latitude",
                    "longitude"
                )
                VALUES {values_clause}
                """)

                bind_params = {}
                for i, row in enumerate(location_rows):
                    bind_params[f"code{i}"] = row["code"]
                    bind_params[f"displayName{i}"] = row["displayName"]
                    bind_params[f"notes{i}"] = row["notes"]
                    bind_params[f"latitude{i}"] = row["latitude"]
                    bind_params[f"longitude{i}"] = row["longitude"]

                # perform a single insert statement for all rows
                stmt = stmt.bindparams(**bind_params)
                conn.execute(stmt)

                # dynamically create the values clause for the mapping table
                values_clause = ", ".join(
                    f"(:dataLocationCode{i}, :dataSourceCode{i}, :dataSourceLocationCode{i}, :priorityOrder{i})"
                    for i in range(len(mapping_rows))
                )

                stmt = text(f"""
                INSERT INTO "dataLocation_dataSource_mapping" (
                    "dataLocationCode",
                    "dataSourceCode",
                    "dataSourceLocationCode",
                    "priorityOrder"
                )
                VALUES {values_clause}
                """)

                bind_params = {}
                for i, row in enumerate(mapping_rows):
                    bind_params[f"dataLocationCode{i}"] = row["dataLocationCode"]
                    bind_params[f"dataSourceCode{i}"] = row["dataSourceCode"]
                    bind_params[f"dataSourceLocationCode{i}"] = row["dataSourceLocationCode"]
                    bind_params[f"priorityOrder{i}"] = int(row["priorityOrder"])

                # perform a single insert statement for all rows
                stmt = stmt.bindparams(**bind_params)
                conn.execute(stmt)

        return True
    
    def _read_rows(self) -> tuple[list[dict], list[dict]]:
        """
        This function reads rows from the dataLocation.csv and dataMapping.csv files and returns them
        as a list of dictionaries

        :return tuple[list[dict], list[dict]] - a tuple of 2 lists of dictionaries representing each row in the csv files.
            The first element is the list of dictionaries from the dataLocation csv file
            and the second element is the list of dictionaries from the dataMapping csv file.
        """

        # read rows that were added from the data location csv file
        with open(f'{LOCATION_CSV}', mode='r') as file:
            location_rows = [row for row in csv.DictReader(file)]

        # read rows that were added from the data mapping csv file
        with open(f'{MAPPING_CSV}', mode='r') as file:
            mapping_rows = [row for row in csv.DictReader(file)]

        return location_rows, mapping_rows


    def rollback(self, databaseEngine: Engine) -> bool:
        """Roll version 3.8 back without deleting pre-existing input/output data.

        Only mapping pairs and reference locations created by this migration are
        removed. Existing data that references a location causes the transaction
        to fail through its foreign-key constraint instead of being deleted.
        """
        location_rows, mapping_rows = self._read_rows()
        with databaseEngine.begin() as connection:
            helper = DatabaseDeletionHelper(connection)
            for row in mapping_rows:
                helper.delete_mapping_row(row["dataLocationCode"], row["dataSourceCode"])
            for row in location_rows:
                helper.delete_reference_row("ref_dataLocation", row["code"])
        helper.write_deletion_dump()
        return True
