from __future__ import annotations

import argparse
import asyncio
import json
from typing import TypeAlias

from fastmcp import Client


EXPECTED_TOOLS = {
    "search_jobs",
    "get_job",
    "add_job",
    "update_job",
    "delete_job",
    "list_companies",
    "add_company",
    "update_company",
    "get_company",
    "get_company_jobs",
    "submit_mock_application",
    "get_application_status",
    "update_application_status",
    "list_mock_applications",
    "reset_mock_data",
}

SmokeTestValue: TypeAlias = str | int | list[str]
SmokeTestResult: TypeAlias = dict[str, SmokeTestValue]


async def run_smoke_test(url: str) -> SmokeTestResult:
    client = Client(url)

    async with client:
        await client.ping()

        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        missing_tools = sorted(EXPECTED_TOOLS - tool_names)
        if missing_tools:
            raise AssertionError(f"Missing expected tools: {missing_tools}")

        reset_result = await client.call_tool("reset_mock_data", {"scope": "all"})
        reset_data = reset_result.data
        if not isinstance(reset_data, dict) or not reset_data.get("reset"):
            raise AssertionError(f"Unexpected reset result: {reset_data!r}")

        search_result = await client.call_tool(
            "search_jobs",
            {"query": "engineer", "work_mode": "remote", "limit": 5},
        )
        search_data = search_result.data
        if not isinstance(search_data, dict) or search_data.get("total", 0) < 1:
            raise AssertionError(f"Unexpected search result: {search_data!r}")

        first_job = search_data["jobs"][0]
        job_id = first_job["id"]

        get_job_result = await client.call_tool("get_job", {"job_id": job_id})
        get_job_data = get_job_result.data
        if not isinstance(get_job_data, dict) or not get_job_data.get("found"):
            raise AssertionError(f"Unexpected get_job result: {get_job_data!r}")

        company_id = first_job["company_id"]
        company_jobs_result = await client.call_tool("get_company_jobs", {"company_id": company_id})
        company_jobs_data = company_jobs_result.data
        if not isinstance(company_jobs_data, dict) or not company_jobs_data.get("found"):
            raise AssertionError(f"Unexpected company jobs result: {company_jobs_data!r}")

        submit_result = await client.call_tool(
            "submit_mock_application",
            {
                "job_id": job_id,
                "applicant_name": "Smoke Test",
                "applicant_email": "smoke@example.com",
                "resume_url": "https://example.com/resume.pdf",
                "cover_note": "Smoke test application",
            },
        )
        submit_data = submit_result.data
        if not isinstance(submit_data, dict) or not submit_data.get("submitted"):
            raise AssertionError(f"Unexpected submit result: {submit_data!r}")

        application_id = submit_data["application"]["id"]
        application_number = submit_data["application_number"]

        if application_number != application_id:
            raise AssertionError(f"Unexpected application number: {submit_data!r}")

        status_result = await client.call_tool(
            "get_application_status",
            {"application_number": application_number},
        )
        status_data = status_result.data
        if not isinstance(status_data, dict) or not status_data.get("found"):
            raise AssertionError(f"Unexpected application status result: {status_data!r}")

        applications_result = await client.call_tool(
            "list_mock_applications",
            {"job_id": job_id},
        )
        applications_data = applications_result.data
        if not isinstance(applications_data, dict):
            raise AssertionError(f"Unexpected applications result: {applications_data!r}")

        application_ids = [item["id"] for item in applications_data["applications"]]
        if application_id not in application_ids:
            raise AssertionError(
                f"Expected application {application_id} in application list: {application_ids}"
            )

    return {
        "status": "ok",
        "url": url,
        "tools_checked": sorted(EXPECTED_TOOLS),
        "searched_job_id": job_id,
        "submitted_application_id": application_id,
        "matching_applications": len(application_ids),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an MCP smoke test against jobmcp.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/mcp",
        help="MCP endpoint URL",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_smoke_test(args.url))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
