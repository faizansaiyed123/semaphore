# -*- coding: utf-8 -*-
#3_3_DatabaseMigration.py
#----------------------------------
# Created By: Savannah Stephenson
# Created Date: 10/06/2025
#----------------------------------
"""This is a database migration script that will update to version
    3.3 of the database. The intended change is to add the NDFD_JSON
    data source to the ref_dataSource table.
 """ 
#----------------------------------
# 
#
#Imports
from DatabaseMigration.IDatabaseMigration import IDatabaseMigration
from DatabaseMigration.databaseMigrationUtility import DatabaseDeletionHelper
from sqlalchemy import Engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert
import csv

#Constants
CSV_FILE_PATHS = './tools/DatabaseMigration/3_3/init_data'


class Migrator(IDatabaseMigration):

    def update(self, databaseEngine: Engine) -> bool:
        """This function updates the database to version 3.3 which adds the NDFD_JSON
           data source to the ref_dataSource table.

           :param databaseEngine: Engine - the engine of the database we are connecting to (semaphore)
           :return: bool indicating successful update
        """
        # Setting engine
        self.__engine = databaseEngine

        # Reflect the tables from the database that we want to add data too
        metadata = MetaData()
        metadata.reflect(bind=databaseEngine)
        
        ref_dataSource = metadata.tables['ref_dataSource']

        # Read in the data based off of csv files
        new_data = self.__readInitCSV('newRows.csv')
        results = self.insert_ref_data(new_data, ref_dataSource)

        return True if len(results) == 1 else False
    
    def __readInitCSV(self, csvFileName: str) -> list:
        """This function reads in a CSV file with the data needed for the initialization 
            of the database
            :param csvFileName: str - CSV file name
            
            :return: list of dictionaries
        """
        csvFilePath = f'{CSV_FILE_PATHS}/{csvFileName}'
        dictionaryList = []
        with open(csvFilePath, mode = 'r') as infile:
            csvDict = csv.DictReader(infile)
            for dictionary in csvDict:
                dictionaryList.append(dictionary)

        return dictionaryList
    
    def insert_ref_data(self, rows: list[dict], table: Table) -> list[tuple]:
        """This method inserts reference rows
            :param rows: A list of dictionaries containing data source information
            :return Series - SQLALCHEMY tupleish rows
        """
        with self.__engine.connect() as conn:
            cursor = conn.execute(insert(table)
                                  .returning(table)
                                  .values(rows)
                                  )
            result = cursor.fetchall()
            conn.commit()
        return result

    def rollback(self, databaseEngine: Engine) -> bool:
        """Roll version 3.3 back without deleting data that uses NDFD_JSON."""
        source_rows = self.__readInitCSV('newRows.csv')
        with databaseEngine.begin() as connection:
            helper = DatabaseDeletionHelper(connection)
            for row in source_rows:
                # The FK protects any inputs that still depend on this source.
                helper.delete_reference_row("ref_dataSource", row["code"])
        helper.write_deletion_dump()
        return True
