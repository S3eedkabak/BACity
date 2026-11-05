"""Publish real JUnit counts; missing, empty, failed or skipped suites fail CI."""
import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def counts(path):
    cases = list(ET.parse(path).iter('testcase'))
    skipped = sum(case.find('skipped') is not None for case in cases)
    failed = sum(case.find('failure') is not None or case.find('error') is not None for case in cases)
    return len(cases) - failed - skipped, failed, skipped, len(cases)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--label', required=True)
    args = parser.parse_args(argv)
    try:
        passed, failed, skipped, total = counts(args.report)
    except (OSError, ET.ParseError) as error:
        message = f'{args.label}: no valid test report ({error}). Tests did not finish reporting.'
        status = 1
    else:
        message = f'{args.label}: {passed} passed, {failed} failed, {skipped} skipped; {total} collected.'
        status = int(total == 0 or failed > 0 or skipped > 0)
        if skipped:
            message += ' Unexpected skips fail CI; restore the required fixture/service instead of bypassing tests.'
        if not total:
            message += ' An empty suite is not a pass.'
    print(message)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
            summary.write(message + '\n\n')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
