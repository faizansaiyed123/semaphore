# -*- coding: utf-8 -*-
#3_1_DatabaseMigration.py
#----------------------------------
# Created By: Jeremiah Sosa
# Created Date:04/13/2025
# Version 1.0
#----------------------------------
"""This is a database migration script that will update to version
    3.1 of the database. The intended change is add source for TWC
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
CSV_FILE_PATHS = './tools/DatabaseMigration/3_1/init_data'


class Migrator(IDatabaseMigration):

    def update(self, databaseEngine: Engine) -> bool:
        """This function updates the database to version 3.1 which update Source descriptions

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
            :param rows: A list of dictionaries. The dict can be found in NOTE 1
            :return Series - SQLALCHEMY tupleish rows
            NOTE:: {"code": None, "displayName": None, "notes": None, "latitude": None, "longitude": None}
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
        """Roll version 3.1 back without deleting data that uses the new source."""
        source_rows = self.__readInitCSV('newRows.csv')
        with databaseEngine.begin() as connection:
            helper = DatabaseDeletionHelper(connection)
            for row in source_rows:
                # The FK protects any inputs that still depend on this source.
                helper.delete_reference_row("ref_dataSource", row["code"])
        helper.write_deletion_dump()
        return True
