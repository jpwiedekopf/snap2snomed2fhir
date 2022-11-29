# This is a sample Python script.
import datetime
from dataclasses import dataclass
from typing import Dict, Optional
import json
import click
import inquirer
import pandas
from fhirclient.models import conceptmap
from pandas import DataFrame
from rich import print


@dataclass
class Arguments:
    input_filename: str
    output_filename: str
    url: Optional[str]
    version: Optional[str]
    name: Optional[str]
    title: Optional[str]
    id: Optional[str]

    def __init__(self,
                 input_filename: str,
                 output_filename: str,
                 url: Optional[str],
                 version: Optional[str],
                 name: Optional[str],
                 title: Optional[str],
                 id: Optional[str],
                 status: Optional[str]):
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.url = url
        self.version = version
        self.name = name
        self.title = title
        self.id = id
        self.status = status


class ColumnMap:
    source_code = "Source code"
    source_display = "Source display"
    target_code = "Target code"
    target_display = "Target display"
    relationship = "Relationship type code"
    relationship_display = "Relationship type display"
    no_map_flag = "No map flag"
    status = "Status"


class Snap2Snomed2Fhir:
    column_map = ColumnMap()
    equivalence_map = {
        ("TARGET_BROADER", "False"): "wider",
        ("TARGET_EQUIVALENT", "False"): "equivalent",
        ("TARGET_NARROWER", "False"): "narrower",
        ("TARGET_INEXACT", "False"): "inexact",
        ("nan", "True"): "unmatched",
    }

    def __init__(self, args: Arguments):
        self.args = args

    def write_cm(self, cm: conceptmap.ConceptMap):
        with open(self.args.output_filename, "w", encoding="utf-8") as of:
            j = cm.as_json()
            json.dump(j, of, indent=2)
        print(f"Wrote to: {self.args.output_filename}")

    def snap2snomed2fhir(self):
        df = self.read_workbook()
        cm = self.map2fhir(df)
        self.write_cm(cm)

    def read_workbook(self) -> DataFrame:
        with open(self.args.input_filename, "rb") as ef:
            df = pandas.read_excel(ef, sheet_name=0, header=0, dtype=str)
            return df

    def map_target(self, row: Dict) -> [conceptmap.ConceptMapGroupElementTarget, None]:
        snap_equivalence = str(row[self.column_map.relationship])
        snap_no_map = row[self.column_map.no_map_flag]
        equivalence = self.equivalence_map[(snap_equivalence, snap_no_map)]
        if equivalence is None:
            return None
        if self.column_map.target_code in row.keys():
            target_code = row[self.column_map.target_code]
            target_display = row[self.column_map.target_display]
            if equivalence == "unmatched":
                return conceptmap.ConceptMapGroupElementTarget({
                    "equivalence": "unmatched"
                })
            return conceptmap.ConceptMapGroupElementTarget({
                "code": target_code,
                "display": target_display,
                "equivalence": equivalence
            })
        return None

    def map2fhir(self, df: DataFrame) -> conceptmap.ConceptMap:
        questions = []
        if self.args.url is None:
            questions.append(inquirer.Text("url", message="Canonical URL of the ConceptMap"))
        if self.args.version is None:
            questions.append(inquirer.Text("version", message="Version"))
        questions.append(inquirer.List("status", message="Status", choices=["draft", "active", "retired", "unknown"]))
        questions.append(inquirer.List("experimental", message="Experimental", choices=[True, False]))
        if len(questions):
            answers = inquirer.prompt(questions)
        else:
            answers = {}
        answers.update({
            "date": datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-00")
        })
        cm = conceptmap.ConceptMap(answers)
        cm_group = conceptmap.ConceptMapGroup()
        cm_group.element = []
        mappings = {}

        for index, row in df.iterrows():
            row_dict = row.to_dict()
            source_code = row_dict[self.column_map.source_code]
            if source_code in mappings:
                current_map = mappings[source_code]
            else:
                current_map = conceptmap.ConceptMapGroupElement({
                    "code": row_dict[self.column_map.source_code],
                    "display": row_dict[self.column_map.source_display],
                    "target": []
                })
            target = self.map_target(row_dict)
            current_map.target.append(target)
            mappings[source_code] = current_map
        cm_group.element = [element for element in mappings.values()]
        cm.group = [cm_group]
        print(cm.as_json())
        return cm


@click.command()
@click.argument("input_filename", type=click.Path(exists=True))
@click.argument("output_filename", type=click.Path(exists=False, writable=True))
@click.option("--url", "-u", help="The canonical URL of the ConceptMap")
@click.option("--version", "-v", help="The version of the ConceptMap")
@click.option("--name", "-n", help="The name (machine-readable) of the ConceptMap")
@click.option("--title", "-t", help="The title (machine-readable) of the ConceptMap")
@click.option("--id", "-i", help="The ID (<= 64 chars, alphanumeric and `-`) of the ConceptMap")
@click.option("--status", "-s", help="The status of the ConceptMap",
              type=click.Choice(["draft", "active", "retired", "unknown"]))
def snap2snomed2fhir_app(input_filename, output_filename, url, version, name, title, id, status):
    args = Arguments(input_filename=input_filename, output_filename=output_filename, url=url, version=version,
                     name=name, title=title, id=id, status=status)
    print(args)
    Snap2Snomed2Fhir(args).snap2snomed2fhir()


if __name__ == '__main__':
    snap2snomed2fhir_app()
