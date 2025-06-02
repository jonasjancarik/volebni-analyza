#!/usr/bin/env python3
"""
Comprehensive analyzer for Prague 5 election data
"""

import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class Prague5ElectionAnalyzer:
    """
    Statistical analysis and insights generator for Prague 5 election data
    """

    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.results_dir = self.data_dir / "results"
        self.detailed_dir = self.data_dir / "detailed"
        self.reports_dir = self.data_dir / "reports"

        # Ensure reports directory exists
        self.reports_dir.mkdir(exist_ok=True)

        # Load data
        self.detailed_data = self.load_detailed_data()
        self.districts_data = self.load_districts_data()

    def load_detailed_data(self):
        """Load detailed district-level election data"""
        detailed_file = self.detailed_dir / "prague5_detailed_results.json"
        if detailed_file.exists():
            with open(detailed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return pd.DataFrame(data)
        return None

    def load_districts_data(self):
        """Load districts information"""
        districts_file = self.data_dir / "raw" / "prague5_districts.json"
        if districts_file.exists():
            with open(districts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def clean_numeric_data(self, df, column):
        """Clean numeric data by removing spaces and converting to float"""
        if column in df.columns:
            return pd.to_numeric(
                df[column].str.replace(" ", "").str.replace(",", "."), errors="coerce"
            )
        return None

    def prepare_analysis_data(self):
        """Prepare clean data for analysis"""
        if self.detailed_data is None:
            logger.warning("No detailed data available for analysis")
            return None

        # Extract structured data
        structured_data = []
        for _, row in self.detailed_data.iterrows():
            if isinstance(row["structured"], dict):
                data_point = row["structured"].copy()
                data_point["district_id"] = row["district_id"]
                structured_data.append(data_point)

        if not structured_data:
            return None

        df = pd.DataFrame(structured_data)

        # Clean and convert numeric columns
        df["turnout_pct"] = self.clean_numeric_data(df, "Volebníúčast v %")
        df["registered_voters"] = self.clean_numeric_data(df, "Voličiv seznamu")
        df["valid_votes"] = self.clean_numeric_data(df, "Platnéhlasy")
        df["ballots_issued"] = self.clean_numeric_data(df, "Vydanéobálky")
        df["ballots_returned"] = self.clean_numeric_data(df, "Odevzdanéobálky")

        return df

    def calculate_basic_statistics(self, df):
        """Calculate basic statistical measures"""
        stats = {
            "total_districts_analyzed": len(df),
            "total_registered_voters": int(df["registered_voters"].sum()),
            "total_valid_votes": int(df["valid_votes"].sum()),
            "average_turnout": float(df["turnout_pct"].mean()),
            "median_turnout": float(df["turnout_pct"].median()),
            "std_turnout": float(df["turnout_pct"].std()),
            "min_turnout": float(df["turnout_pct"].min()),
            "max_turnout": float(df["turnout_pct"].max()),
            "highest_turnout_district": df.loc[
                df["turnout_pct"].idxmax(), "district_id"
            ],
            "lowest_turnout_district": df.loc[
                df["turnout_pct"].idxmin(), "district_id"
            ],
        }

        # Calculate vote efficiency (valid votes per registered voter)
        df["vote_efficiency"] = df["valid_votes"] / df["registered_voters"]
        stats["avg_vote_efficiency"] = float(df["vote_efficiency"].mean())

        return stats

    def analyze_district_patterns(self, df):
        """Analyze patterns across districts"""
        analysis = {"district_categories": {}, "correlations": {}, "outliers": []}

        # Categorize districts by turnout
        turnout_quartiles = df["turnout_pct"].quantile([0.25, 0.5, 0.75])

        analysis["district_categories"] = {
            "low_turnout": df[df["turnout_pct"] <= turnout_quartiles[0.25]][
                "district_id"
            ].tolist(),
            "medium_turnout": df[
                (df["turnout_pct"] > turnout_quartiles[0.25])
                & (df["turnout_pct"] <= turnout_quartiles[0.75])
            ]["district_id"].tolist(),
            "high_turnout": df[df["turnout_pct"] > turnout_quartiles[0.75]][
                "district_id"
            ].tolist(),
        }

        # Calculate correlations
        numeric_cols = [
            "turnout_pct",
            "registered_voters",
            "valid_votes",
            "vote_efficiency",
        ]
        correlation_matrix = df[numeric_cols].corr()

        analysis["correlations"] = {
            "turnout_vs_district_size": float(
                correlation_matrix.loc["turnout_pct", "registered_voters"]
            ),
            "turnout_vs_efficiency": float(
                correlation_matrix.loc["turnout_pct", "vote_efficiency"]
            ),
        }

        # Identify outliers (districts with unusual patterns)
        z_scores = np.abs(
            (df["turnout_pct"] - df["turnout_pct"].mean()) / df["turnout_pct"].std()
        )
        outlier_threshold = 2.0
        outliers = df[z_scores > outlier_threshold]

        analysis["outliers"] = [
            {
                "district_id": row["district_id"],
                "turnout_pct": float(row["turnout_pct"]),
                "reason": "unusual_turnout",
                "z_score": float(z_scores[idx]),
            }
            for idx, row in outliers.iterrows()
        ]

        return analysis

    def generate_insights(self, stats, patterns):
        """Generate human-readable insights"""
        insights = []

        # Turnout insights
        if stats["average_turnout"] > 50:
            insights.append(
                {
                    "type": "positive",
                    "category": "participation",
                    "text": f"Prague 5 shows strong democratic participation with {stats['average_turnout']:.1f}% average turnout.",
                }
            )
        elif stats["average_turnout"] > 40:
            insights.append(
                {
                    "type": "neutral",
                    "category": "participation",
                    "text": f"Prague 5 has moderate voter turnout at {stats['average_turnout']:.1f}%, typical for municipal elections.",
                }
            )
        else:
            insights.append(
                {
                    "type": "concern",
                    "category": "participation",
                    "text": f"Prague 5 shows low voter turnout at {stats['average_turnout']:.1f}%, suggesting voter apathy.",
                }
            )

        # District variation insights
        turnout_range = stats["max_turnout"] - stats["min_turnout"]
        if turnout_range > 20:
            insights.append(
                {
                    "type": "concern",
                    "category": "equity",
                    "text": f"Large turnout variation ({turnout_range:.1f}% difference) suggests uneven civic engagement across districts.",
                }
            )
        elif turnout_range > 10:
            insights.append(
                {
                    "type": "neutral",
                    "category": "equity",
                    "text": f"Moderate turnout variation ({turnout_range:.1f}% difference) across districts is typical.",
                }
            )
        else:
            insights.append(
                {
                    "type": "positive",
                    "category": "equity",
                    "text": f"Low turnout variation ({turnout_range:.1f}% difference) indicates consistent engagement across districts.",
                }
            )

        # District size correlation insights
        size_correlation = patterns["correlations"]["turnout_vs_district_size"]
        if abs(size_correlation) > 0.5:
            direction = "larger" if size_correlation > 0 else "smaller"
            insights.append(
                {
                    "type": "finding",
                    "category": "patterns",
                    "text": f"Strong correlation found: {direction} districts tend to have higher voter turnout.",
                }
            )

        # Outlier insights
        if patterns["outliers"]:
            outlier_districts = [o["district_id"] for o in patterns["outliers"]]
            insights.append(
                {
                    "type": "finding",
                    "category": "outliers",
                    "text": f"Districts {', '.join(outlier_districts)} show unusual voting patterns and merit further investigation.",
                }
            )

        return insights

    def create_recommendations(self, stats, patterns, insights):
        """Generate actionable recommendations"""
        recommendations = []

        # Based on turnout levels
        if stats["average_turnout"] < 50:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "civic_engagement",
                    "title": "Improve Voter Outreach",
                    "description": "Implement targeted campaigns to increase voter participation, especially in low-turnout districts.",
                    "specific_actions": [
                        "Door-to-door canvassing in low-turnout districts",
                        "Social media campaigns targeting young voters",
                        "Voting education workshops",
                    ],
                }
            )

        # Based on district variations
        low_turnout_districts = patterns["district_categories"]["low_turnout"]
        if low_turnout_districts:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "equity",
                    "title": "Focus on Low-Participation Areas",
                    "description": f"Specifically target districts {', '.join(low_turnout_districts)} for enhanced civic engagement.",
                    "specific_actions": [
                        "Analyze barriers to voting in these districts",
                        "Improve polling station accessibility",
                        "Conduct community meetings to understand local concerns",
                    ],
                }
            )

        # Based on correlations
        size_correlation = patterns["correlations"]["turnout_vs_district_size"]
        if size_correlation < -0.3:  # Smaller districts have higher turnout
            recommendations.append(
                {
                    "priority": "low",
                    "category": "administration",
                    "title": "Evaluate District Sizes",
                    "description": "Consider whether large districts create barriers to civic engagement.",
                    "specific_actions": [
                        "Review optimal district sizes for engagement",
                        "Consider subdividing very large districts",
                        "Improve voting infrastructure in large districts",
                    ],
                }
            )

        return recommendations

    def generate_comprehensive_report(self):
        """Generate a comprehensive analysis report"""
        logger.info("Generating comprehensive Prague 5 election analysis report")

        df = self.prepare_analysis_data()
        if df is None:
            logger.error("Cannot generate report: no data available")
            return None

        # Perform analysis
        stats = self.calculate_basic_statistics(df)
        patterns = self.analyze_district_patterns(df)
        insights = self.generate_insights(stats, patterns)
        recommendations = self.create_recommendations(stats, patterns, insights)

        # Create comprehensive report
        report = {
            "metadata": {
                "title": "Prague 5 Municipal Elections 2022 - Comprehensive Analysis",
                "generated_date": datetime.now().isoformat(),
                "data_coverage": {
                    "total_districts": len(self.districts_data)
                    if self.districts_data
                    else 0,
                    "analyzed_districts": len(df),
                    "coverage_percentage": (len(df) / len(self.districts_data) * 100)
                    if self.districts_data
                    else 0,
                },
            },
            "executive_summary": {
                "key_findings": [
                    f"Average turnout: {stats['average_turnout']:.1f}%",
                    f"Total registered voters: {stats['total_registered_voters']:,}",
                    f"Turnout range: {stats['min_turnout']:.1f}% - {stats['max_turnout']:.1f}%",
                    f"Districts analyzed: {stats['total_districts_analyzed']}",
                ],
                "main_concerns": [
                    insight["text"]
                    for insight in insights
                    if insight["type"] == "concern"
                ],
                "positive_findings": [
                    insight["text"]
                    for insight in insights
                    if insight["type"] == "positive"
                ],
            },
            "detailed_statistics": stats,
            "pattern_analysis": patterns,
            "insights": insights,
            "recommendations": recommendations,
            "data_quality": {
                "completeness": len(df) / len(self.districts_data)
                if self.districts_data
                else 0,
                "data_sources": ["Czech Statistical Office (volby.cz)", "Web scraping"],
                "limitations": [
                    "Limited to 5 districts due to access restrictions",
                    "Manual data collection required due to API limitations",
                    "Geographic data estimated due to incomplete address information",
                ],
            },
        }

        # Save report
        report_file = self.reports_dir / "comprehensive_analysis_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Generate human-readable summary
        self.generate_summary_report(report)

        logger.info(f"Comprehensive report saved to {report_file}")
        return report

    def generate_summary_report(self, report):
        """Generate a human-readable summary report"""
        summary_content = f"""
# Prague 5 Municipal Elections 2022 - Analysis Summary

**Generated:** {datetime.now().strftime("%B %d, %Y")}

## Executive Summary

Prague 5's 2022 municipal election analysis reveals important patterns in voter participation and civic engagement across the analyzed electoral districts.

### Key Statistics
- **Average Turnout:** {report["detailed_statistics"]["average_turnout"]:.1f}%
- **Total Registered Voters:** {report["detailed_statistics"]["total_registered_voters"]:,}
- **Total Valid Votes:** {report["detailed_statistics"]["total_valid_votes"]:,}
- **Districts Analyzed:** {report["detailed_statistics"]["total_districts_analyzed"]} of {report["metadata"]["data_coverage"]["total_districts"]}

### Turnout Analysis
- **Highest Turnout:** District {report["detailed_statistics"]["highest_turnout_district"]} ({report["detailed_statistics"]["max_turnout"]:.1f}%)
- **Lowest Turnout:** District {report["detailed_statistics"]["lowest_turnout_district"]} ({report["detailed_statistics"]["min_turnout"]:.1f}%)
- **Standard Deviation:** {report["detailed_statistics"]["std_turnout"]:.1f}%

## Key Insights

### Positive Findings
"""

        for insight in report["insights"]:
            if insight["type"] == "positive":
                summary_content += f"- {insight['text']}\n"

        summary_content += "\n### Areas of Concern\n"
        for insight in report["insights"]:
            if insight["type"] == "concern":
                summary_content += f"- {insight['text']}\n"

        summary_content += "\n### Notable Patterns\n"
        for insight in report["insights"]:
            if insight["type"] == "finding":
                summary_content += f"- {insight['text']}\n"

        summary_content += "\n## Recommendations\n"
        for rec in report["recommendations"]:
            summary_content += (
                f"\n### {rec['title']} (Priority: {rec['priority'].title()})\n"
            )
            summary_content += f"{rec['description']}\n"
            summary_content += "**Specific Actions:**\n"
            for action in rec["specific_actions"]:
                summary_content += f"- {action}\n"

        summary_content += f"""
## Data Quality & Limitations

**Coverage:** {report["metadata"]["data_coverage"]["coverage_percentage"]:.1f}% of Prague 5 districts analyzed

**Limitations:**
"""
        for limitation in report["data_quality"]["limitations"]:
            summary_content += f"- {limitation}\n"

        summary_content += """
## Next Steps

1. **Expand Data Collection:** Work to access complete district-level data for all 81 Prague 5 districts
2. **Historical Analysis:** Compare with previous election cycles to identify trends
3. **Demographic Correlation:** Analyze relationship between district demographics and voting patterns
4. **Implementation:** Begin implementing high-priority recommendations

---

*This analysis is based on publicly available election data from the Czech Statistical Office and represents a partial view of Prague 5's electoral landscape.*
"""

        # Save summary
        summary_file = self.reports_dir / "analysis_summary.md"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary_content)

        logger.info(f"Summary report saved to {summary_file}")


if __name__ == "__main__":
    analyzer = Prague5ElectionAnalyzer()
    report = analyzer.generate_comprehensive_report()
    if report:
        print("✓ Comprehensive analysis report generated!")
        print(f"✓ Reports saved in data/reports/")
        print(
            f"✓ Key finding: {report['detailed_statistics']['average_turnout']:.1f}% average turnout"
        )
    else:
        print("✗ Could not generate report - insufficient data")
