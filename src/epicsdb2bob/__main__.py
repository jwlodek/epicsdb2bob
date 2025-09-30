"""Interface for ``python -m epicsdb2bob``."""

import logging
import os
from argparse import ArgumentParser
from pathlib import Path

from dbtoolspy import Database, load_database_file, load_template_file

from . import __version__
from .bobfile_gen import generate_bobfile_for_db, generate_bobfile_for_substitution
from .palettes import WIDGET_PALETTES

__all__ = ["main"]

logging.basicConfig()

logger = logging.getLogger("epicsdb2bob")


def main() -> None:
    """Argument parser for the CLI."""
    parser = ArgumentParser()
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "-e",
        "--embed",
        type=str,
        choices=["none", "single", "all"],
        default="single",
        help="Sets whether to embed screens when generating substitution file or not.",
    )
    parser.add_argument(
        "-m",
        "--macros",
        nargs="+",
        type=str,
        help="Macros to apply when loading databases",
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to location in which to search for EPICS database template files",
    )
    parser.add_argument(
        "output", type=str, help="Output location for generated screens."
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )

    parser.add_argument(
        "-t",
        "--title_bar",
        type=str,
        choices=["none", "minimal", "full"],
        default="minimal",
    )

    parser.add_argument(
        "-r",
        "--readback_suffix",
        type=str,
        default="_RBV",
        help="Suffix to check for when matching setpoint and readback records.",
    )
    parser.add_argument(
        "-b",
        "--addtl_bobfile_dirs",
        type=str,
        nargs="+",
        default=[],
        help="Dirs to search for addtl .bob files for generating substitution screens.",
    )
    parser.add_argument(
        "--macro_level",
        type=str,
        default="widget",
        choices=["widget", "screen", "launcher"],
        help="Level at which to apply macros.",
    )
    parser.add_argument(
        "--palette",
        type=str,
        default="default",
        choices=WIDGET_PALETTES.keys(),
        help="Color palette to use.",
    )

    args = parser.parse_args()

    logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)

    macros_dict = {}
    if args.macros:
        split_macros = [macro.split("=") for macro in args.macros]
        for macro in split_macros:
            macros_dict[macro[0]] = macro[1]

    written_bobfiles = {}
    databases = find_epics_dbs_and_templates(
        args.input,
        macros=macros_dict if macros_dict else None,
    )
    for name in databases:
        screen = generate_bobfile_for_db(
            name,
            databases[name],
            title_bar_size=args.title_bar,
            readback_suffix=args.readback_suffix,
            macros=args.macros,
            macro_level=args.macro_level,
            palette=args.palette,
        )
        if args.macro_level == "screen":
            for macro in args.macros or []:
                key, value = macro.split("=")
                screen.macro(key, value)

        logger.info(f"Generated screen for database: {name}")
        output_filepath = os.path.join(args.output, f"{name}.bob")
        screen.write_screen(output_filepath)
        written_bobfiles[os.path.basename(output_filepath)] = output_filepath

    for addtl_bobfile_dir in args.addtl_bobfile_dirs:
        for dirpath, _, filenames in os.walk(addtl_bobfile_dir):
            for filename in filenames:
                if filename.endswith((".bob", ".opi")):
                    full_path = os.path.join(dirpath, filename)
                    written_bobfiles[filename] = full_path

    substitutions = find_epics_subs(args.input)
    for substitution in substitutions:
        screen = generate_bobfile_for_substitution(
            substitution,
            substitutions[substitution],
            written_bobfiles,
            args.embed,
            args.palette,
            args.macro_level,
        )

        logger.info(f"Generated screen for substitution: {substitution}")
        output_filepath = os.path.join(args.output, f"{substitution}.bob")
        screen.write_screen(output_filepath)
        written_bobfiles[os.path.basename(output_filepath)] = output_filepath


def find_epics_dbs_and_templates(
    search_path: Path, macros: dict[str, str] | None = None
) -> dict[str, Database]:
    epics_databases: dict[str, Database] = {}
    for dirpath, _, filenames in os.walk(search_path):
        for file in filenames:
            full_file_path = os.path.join(dirpath, file)
            if file.endswith((".db", ".template")):
                try:
                    epics_databases[file.split(".", -1)[0]] = load_database_file(
                        full_file_path, macros=macros, load_includes=False
                    )
                    print(epics_databases.keys())
                    logger.info(f"Parsed {full_file_path}")
                except StopIteration:
                    logger.warning(
                        f"Failed to parse {full_file_path} as an EPICS database"
                    )

    return epics_databases


def find_epics_subs(search_path: Path) -> dict[str, dict[str, list[dict[str, str]]]]:
    epics_subs: dict[str, dict[str, list[dict[str, str]]]] = {}
    for dirpath, _, filenames in os.walk(search_path):
        for file in filenames:
            full_file_path = os.path.join(dirpath, file)
            if file.endswith(".substitutions"):
                try:
                    dbs_and_macros: list[tuple[str, dict[str, str]]] = (
                        load_template_file(full_file_path)
                    )
                    epics_sub = {}
                    logger.info(f"Parsed {full_file_path}")
                    for db_name, macros in dbs_and_macros:
                        epics_sub.setdefault(db_name, []).append(macros)
                    epics_subs[os.path.splitext(file)[0]] = epics_sub
                except Exception as e:
                    logger.warning(
                        f"Failed to parse {full_file_path} as an EPICS subs file: {e}"
                    )

    return epics_subs


if __name__ == "__main__":
    main()
