# This is a sample Python script.
import datetime
from dataclasses import dataclass
from typing import Dict, Optional, Any, Union
import json
import click
import inquirer
import pandas
from fhirclient.models import conceptmap
from pandas import DataFrame
from rich import print


def validate_inquirer(_, current: str) -> bool:
    if not current:
        raise inquirer.errors.ValidationError(
            '', reason="The element may not be blank")
    else:
        return True


@dataclass
class Arguments:
    input_filename: str
    output_filename: str
    url: Optional[str]
    version: Optional[str]
    name: Optional[str]
    title: Optional[str]
    id: Optional[str]
    status: Optional[str]
    experimental: Optional[bool]
    group_source: Optional[str]
    target_uri: Optional[str]
    group_source: Optional[str]
    group_source_version: Optional[str]
    group_target: Optional[str]
    group_target_version: Optional[str]

    def __init__(self, input_filename: str, output_filename: str, url: Optional[str], version: Optional[str],
                 name: Optional[str], title: Optional[str], id: Optional[str], status: Optional[str],
                 experimental: Optional[str], source_uri: Optional[str], target_uri: Optional[str],
                 group_source: Optional[str], group_source_version: Optional[str], group_target: Optional[str],
                 group_target_version: Optional[str]):
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.url = url
        self.version = version
        self.name = name
        self.title = title
        self.id = id
        self.status = status
        if experimental == 'true':
            self.experimental = True
        elif experimental == 'false':
            self.experimental = False
        else:
            self.experimental = None
        self.source_uri = source_uri
        self.target_uri = target_uri
        self.group_source = group_source
        self.group_source_version = group_source_version
        self.group_target = group_target
        self.group_target_version = group_target_version


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

    def map_target(self, row: Dict) -> Optional[conceptmap.ConceptMapGroupElementTarget]:
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
        answers = {
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:00Z")
        }

        question_map: Dict[str, tuple[Union[str, bool], inquirer.questions.Question]] = {
            "url": (self.args.url, inquirer.Text("url", message="Canonical URL of the ConceptMap", validate=validate_inquirer)),
            "version": (self.args.version, inquirer.Text("version", message="Version", validate=validate_inquirer)),
            "id": (self.args.id, inquirer.Text("id", message="ID", validate=validate_inquirer)),
            "name": (self.args.name, inquirer.Text("name", message="Name (for machines)", validate=validate_inquirer)),
            "title": (self.args.title, inquirer.Text("title", message="Title (for humans)", validate=validate_inquirer)),
            "status": (self.args.status, inquirer.List("status",
                                                       message="Status",
                                                       choices=["draft", "active", "retired", "unknown"], validate=validate_inquirer)),
            "experimental": (self.args.experimental, inquirer.List("experimental",
                                                                   message="Experimental",
                                                                   choices=[True, False], validate=validate_inquirer)),
            "sourceUri": (self.args.source_uri, inquirer.Text("sourceUri", message="Source URI of the VS for the CM context",
                                                              validate=validate_inquirer)),
            "targetUri": (self.args.source_uri, inquirer.Text("targetUri", message="Target URI of the VS for the CM context",
                                                              validate=validate_inquirer)),
        }

        for answer_key, (answer_value, question) in question_map.items():
            if answer_value is None:
                questions.append(question)
            else:
                answers[answer_key] = answer_value

        if len(questions):
            answers.update(inquirer.prompt(questions))

        group_question_map: Dict[str, tuple[str, inquirer.questions.Question]] = {
            "source": (self.args.group_source, inquirer.Text("source", message="Group source URI", validate=validate_inquirer)),
            "sourceVersion": (self.args.group_source_version, inquirer.Text("sourceVersion", message="Group source version")),
            "target": (self.args.group_target, inquirer.Text("target", message="Target source URI", validate=validate_inquirer)),
            "targetVersion": (self.args.group_target_version, inquirer.Text("targetVersion", message="Target source version")),
        }

        group_questions = []
        group_answers = {
            "element": []
        }
        for answer_key, (answer_value, question) in group_question_map.items():
            if answer_value is None:
                group_questions.append(question)
            else:
                group_answers[answer_key] = answer_value
        if len(group_questions):
            group_answers.update(inquirer.prompt(group_questions))

        

        cm = conceptmap.ConceptMap(answers)
        cm_group = conceptmap.ConceptMapGroup(group_answers) 
        f_json = cm.as_json()
        f_json["group"] = [
            group_answers
        ]
        print(f_json)
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
        # print(cm.as_json())
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
@click.option("--experimental", "-e", help="Whether the CM is experimental",
              type=click.Choice(["True", "False", "true", "false"]))
@click.option("--source-uri", help="The source VS URI of the ConceptMap")
@click.option("--target-uri", help="The target VS URI of the ConceptMap")
@click.option("--group-source", help="The source CS URI of the ConceptMap group")
@click.option("--group-source-version", help="The source CS version of the ConceptMap group")
@click.option("--group-target", help="The target CS URI of the ConceptMap group")
@click.option("--group-target-version", help="The target CS version of the ConceptMap group")
def snap2snomed2fhir_app(input_filename: str, output_filename: str, url: str, version: str,
                         name: str, title: str, id, status: str,
                         experimental: str, source_uri: str, target_uri: str,
                         group_source: str, group_source_version: str, group_target: str,
                         group_target_version: str):
    args = Arguments(input_filename=input_filename, output_filename=output_filename, url=url,
                     version=version, name=name, title=title, id=id,
                     status=status, experimental=experimental.lower(), source_uri=source_uri,
                     target_uri=target_uri, group_source=group_source, group_source_version=group_source_version,
                     group_target=group_target, group_target_version=group_target_version)
    print(args)
    Snap2Snomed2Fhir(args).snap2snomed2fhir()


if __name__ == '__main__':
    snap2snomed2fhir_app()
