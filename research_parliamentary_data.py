#!/usr/bin/env python3
"""
Research script to investigate Czech parliamentary election data structure

This script helps analyze the data structure of parliamentary elections
to inform the implementation of parliamentary election support.

Usage:
    python research_parliamentary_data.py --election ps2021
    python research_parliamentary_data.py --election ps2021 --download-samples
"""

import requests
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_url_accessibility(url: str) -> bool:
    """Test if a URL is accessible"""
    try:
        response = requests.head(url, timeout=10)
        return response.status_code == 200
    except:
        return False


def download_file(url: str, output_path: Path) -> bool:
    """Download a file from URL to output path"""
    try:
        logger.info(f"Downloading {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        logger.info(f"✅ Downloaded to {output_path}")
        logger.info(f"   Size: {len(response.content):,} bytes")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to download {url}: {e}")
        return False


def analyze_xml_structure(xml_file: Path) -> dict:
    """Analyze XML file structure and extract metadata"""
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Get all unique element names at different depths
        def get_element_info(element, depth=0, max_depth=3):
            info = {
                "tag": element.tag,
                "depth": depth,
                "attributes": list(element.attrib.keys()),
                "sample_attributes": dict(list(element.attrib.items())[:3]),
                "text_sample": (
                    element.text[:50] if element.text and element.text.strip() else None
                ),
                "children": [],
            }

            if depth < max_depth:
                for child in element:
                    info["children"].append(
                        get_element_info(child, depth + 1, max_depth)
                    )

            return info

        structure = {
            "root": get_element_info(root),
            "namespace": root.tag.split("}")[0][1:] if "}" in root.tag else None,
            "file": str(xml_file),
            "size_bytes": xml_file.stat().st_size,
        }

        return structure

    except Exception as e:
        logger.error(f"Error analyzing {xml_file}: {e}")
        return None


def research_parliamentary_elections(election_id: str, download_samples: bool = False):
    """Research parliamentary election data structure"""

    logger.info("=" * 80)
    logger.info(f"PARLIAMENTARY ELECTION DATA STRUCTURE RESEARCH: {election_id}")
    logger.info("=" * 80)

    # Expected URLs based on municipal elections pattern
    base_url = f"https://www.volby.cz/pls/{election_id}"
    opendata_url = f"https://www.volby.cz/opendata/{election_id}/xml"

    # Expected file names (hypothesis based on naming patterns)
    expected_files = [
        "psrkoko.xml",  # Electoral districts registry
        "psros.xml",  # Party results
        "pskandl.xml",  # Candidate lists (hypothesis)
        "ps.xml",  # General info (hypothesis)
    ]

    results = {
        "election_id": election_id,
        "base_url": base_url,
        "opendata_url": opendata_url,
        "url_tests": {},
        "downloaded_files": {},
        "structure_analysis": {},
    }

    # Test URL accessibility
    logger.info("\n📡 Testing URL accessibility...")
    urls_to_test = {
        "base": base_url,
        "opendata": opendata_url,
    }

    for name, url in urls_to_test.items():
        accessible = test_url_accessibility(url)
        results["url_tests"][name] = {"url": url, "accessible": accessible}
        logger.info(f"  {'✅' if accessible else '❌'} {name}: {url}")

    # Try to download expected files
    if download_samples:
        logger.info("\n📥 Attempting to download sample files...")
        research_dir = Path("research/parliamentary") / election_id
        research_dir.mkdir(parents=True, exist_ok=True)

        for filename in expected_files:
            url = f"{opendata_url}/{filename}"
            output_path = research_dir / filename

            success = download_file(url, output_path)
            results["downloaded_files"][filename] = {
                "url": url,
                "success": success,
                "path": str(output_path) if success else None,
            }

            # Analyze downloaded file
            if success and output_path.exists():
                logger.info(f"\n🔍 Analyzing {filename}...")
                structure = analyze_xml_structure(output_path)
                if structure:
                    results["structure_analysis"][filename] = structure

                    # Print summary
                    logger.info(f"   Root element: {structure['root']['tag']}")
                    logger.info(f"   Namespace: {structure['namespace']}")
                    logger.info(f"   Size: {structure['size_bytes']:,} bytes")

                    if structure["root"]["children"]:
                        child_types = set(
                            c["tag"] for c in structure["root"]["children"]
                        )
                        logger.info(f"   Child elements: {', '.join(child_types)}")

    # Save research results
    output_file = Path("research") / f"{election_id}_research_results.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"\n💾 Research results saved to: {output_file}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("RESEARCH SUMMARY")
    logger.info("=" * 80)

    accessible_urls = sum(1 for r in results["url_tests"].values() if r["accessible"])
    logger.info(f"✅ Accessible URLs: {accessible_urls}/{len(results['url_tests'])}")

    if download_samples:
        downloaded = sum(
            1 for r in results["downloaded_files"].values() if r["success"]
        )
        logger.info(f"✅ Downloaded files: {downloaded}/{len(expected_files)}")
        logger.info(f"✅ Analyzed structures: {len(results['structure_analysis'])}")

    logger.info("\n📋 Next Steps:")
    if accessible_urls > 0:
        logger.info("   1. Review downloaded samples in research/parliamentary/")
        logger.info("   2. Compare with municipal election structure")
        logger.info("   3. Document differences in PARLIAMENTARY_ELECTIONS_RESEARCH.md")
        logger.info("   4. Create ElectoralDistrictInfo dataclass")
        logger.info("   5. Create ParliamentaryScraper class")
    else:
        logger.info("   1. Verify election_id is correct (try ps2021, ps2017)")
        logger.info("   2. Check if data is available on volby.cz")
        logger.info("   3. Try alternative URLs or file names")

    return results


def compare_with_municipal():
    """Compare parliamentary structure with known municipal structure"""
    logger.info("\n" + "=" * 80)
    logger.info("COMPARING WITH MUNICIPAL ELECTIONS")
    logger.info("=" * 80)

    comparison = {
        "Geographic Unit": {
            "Municipal": "6,377+ municipalities",
            "Parliamentary": "14 electoral districts (kraje)",
        },
        "Registry File": {
            "Municipal": "kvcoco.xml (municipality codes, mandates)",
            "Parliamentary": "psrkoko.xml (district codes, seats) [HYPOTHESIS]",
        },
        "Results File": {
            "Municipal": "kvros.xml (party results by municipality)",
            "Parliamentary": "psros.xml (party results by district) [HYPOTHESIS]",
        },
        "Detail Level": {
            "Municipal": "vysledky_okrsky (polling station level)",
            "Parliamentary": "Similar structure expected",
        },
        "Key Differences": [
            "Parliamentary: 14 districts vs 6,377+ municipalities",
            "Parliamentary: National seat allocation with 5% threshold",
            "Parliamentary: Preferential voting data",
            "Parliamentary: Coalition handling (10% threshold)",
        ],
    }

    for category, items in comparison.items():
        logger.info(f"\n{category}:")
        if isinstance(items, dict):
            for key, value in items.items():
                logger.info(f"  {key}: {value}")
        else:
            for item in items:
                logger.info(f"  • {item}")


def main():
    parser = argparse.ArgumentParser(
        description="Research parliamentary election data structure from ČSÚ"
    )
    parser.add_argument(
        "--election",
        "-e",
        default="ps2021",
        help="Election ID to research (default: ps2021)",
    )
    parser.add_argument(
        "--download-samples",
        "-d",
        action="store_true",
        help="Download sample files for analysis",
    )
    parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Show comparison with municipal elections",
    )

    args = parser.parse_args()

    if args.compare:
        compare_with_municipal()
        return

    results = research_parliamentary_elections(
        election_id=args.election, download_samples=args.download_samples
    )

    # Print instructions
    logger.info("\n" + "=" * 80)
    logger.info("USAGE TIPS")
    logger.info("=" * 80)
    logger.info("\nTo download and analyze samples:")
    logger.info(
        "  python research_parliamentary_data.py --election ps2021 --download-samples"
    )
    logger.info("\nTo compare structures:")
    logger.info("  python research_parliamentary_data.py --compare")
    logger.info("\nTo test different elections:")
    logger.info(
        "  python research_parliamentary_data.py --election ps2017 --download-samples"
    )
    logger.info(
        "  python research_parliamentary_data.py --election ps2013 --download-samples"
    )


if __name__ == "__main__":
    main()
