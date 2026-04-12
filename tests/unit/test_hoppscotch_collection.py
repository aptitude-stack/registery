"""Checks for the Hoppscotch-compatible collection export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.unit
def test_hoppscotch_collection_matches_bruno_workspace_shape() -> None:
    path = Path("hoppscotch/aptitude.postman_collection.json")

    assert path.exists()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["info"]["name"] == "Aptitude"
    assert document["info"]["schema"] == (
        "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    )

    folders = {item["name"]: item for item in document["item"]}
    assert set(folders) == {"Positive", "Negative"}
    assert len(folders["Positive"]["item"]) == 14
    assert len(folders["Negative"]["item"]) == 9

    variable_names = {variable["key"] for variable in document["variable"]}
    assert variable_names >= {
        "baseUrl",
        "readToken",
        "publishToken",
        "adminToken",
        "runId",
        "sanity_version_1",
        "sanity_version_2",
        "negative_missing_version",
        "invalid_version",
        "sanity_dependency_slug",
        "sanity_extension_slug",
        "sanity_overlap_slug",
        "sanity_primary_slug",
        "negative_invalid_slug",
        "negative_duplicate_slug",
        "negative_missing_slug",
        "sanity_primary_content_digest",
    }


@pytest.mark.unit
def test_hoppscotch_collection_preserves_core_request_names_and_order() -> None:
    document = json.loads(
        Path("hoppscotch/aptitude.postman_collection.json").read_text(encoding="utf-8")
    )
    folders = {item["name"]: item["item"] for item in document["item"]}

    positive_names = [item["name"] for item in folders["Positive"]]
    negative_names = [item["name"] for item in folders["Negative"]]

    assert positive_names[:3] == ["Healthz", "Readyz", "Metrics"]
    assert positive_names[-2:] == [
        "Discover Published Skill Candidates",
        "Resolve Published Skill Dependencies",
    ]
    assert negative_names[:3] == [
        "Publish Invalid Request",
        "Seed Duplicate Skill Version",
        "Publish Duplicate Skill Version",
    ]
    assert negative_names[-2:] == ["Resolve Invalid Version", "Resolve Missing Skill Version"]


@pytest.mark.unit
def test_hoppscotch_collection_keeps_publish_requests_as_multipart_with_bundle_files() -> None:
    document = json.loads(
        Path("hoppscotch/aptitude.postman_collection.json").read_text(encoding="utf-8")
    )

    publish_request_names = {
        "Publish Dependency Skill",
        "Publish Extension Skill",
        "Publish Overlap Skill",
        "Publish Skill v1",
        "Publish Skill v2",
        "Publish Invalid Request",
        "Seed Duplicate Skill Version",
        "Publish Duplicate Skill Version",
    }

    requests = {
        item["name"]: item["request"]
        for folder in document["item"]
        for item in folder["item"]
    }

    for request_name in publish_request_names:
        request = requests[request_name]
        body = request["body"]
        assert body["mode"] == "formdata"

        formdata_parts = {part["key"]: part for part in body["formdata"]}
        assert formdata_parts["metadata"]["type"] == "text"
        assert formdata_parts["bundle"]["type"] == "file"
        assert formdata_parts["bundle"]["src"].endswith(".tar.zst")
