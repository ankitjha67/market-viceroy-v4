"""Tests for the 13F source (information-table parse + QoQ diff)."""

from __future__ import annotations

from mv.intelligence.sources.sec_13f import Holding, holdings_diff, parse_information_table

_XML = """<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>915560</value>
    <shrsOrPrnAmt><sshPrnamt>5000000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>100000</value>
    <shrsOrPrnAmt><sshPrnamt>546000</sshPrnamt></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>BROKEN ROW</nameOfIssuer>
  </infoTable>
</informationTable>
"""


def test_parse_information_table_namespace_tolerant() -> None:
    holdings = parse_information_table(_XML)
    assert len(holdings) == 2  # broken row drops
    assert holdings[0].issuer == "APPLE INC"
    assert holdings[0].value_kusd == 915560


def test_holdings_diff_aggregates_lots_and_classifies_changes() -> None:
    previous = [
        Holding("APPLE INC", "037833100", 800000, 4500000),
        Holding("EXITED CO", "111111111", 50000, 100000),
    ]
    current = parse_information_table(_XML)  # apple in two lots -> 1015560 total
    changes = holdings_diff(previous, current)
    by_kind = {c.kind: c for c in changes}
    assert by_kind["increased"].cusip == "037833100"
    assert by_kind["increased"].value_kusd_after == 1015560  # lots aggregated
    assert by_kind["exited"].cusip == "111111111"
    # Largest absolute move first (apple +215560 vs exited -50000).
    assert changes[0].kind == "increased"
