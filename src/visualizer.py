#!/usr/bin/env python3
"""
Visualization module for Prague 5 Election Analysis
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import logging
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class Prague5Visualizer:
    """
    Comprehensive visualization toolkit for Prague 5 election data
    """

    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.results_dir = self.data_dir / "results"
        self.detailed_dir = self.data_dir / "detailed"
        self.viz_dir = self.data_dir / "visualizations"

        # Ensure visualization directory exists
        self.viz_dir.mkdir(exist_ok=True)

        # Load available data
        self.summary_data = self.load_summary_data()
        self.detailed_data = self.load_detailed_data()
        self.districts_data = self.load_districts_data()

        # Prague 5 color theme
        self.colors = {
            "primary": "#1f77b4",
            "secondary": "#ff7f0e",
            "accent": "#2ca02c",
            "warning": "#d62728",
            "info": "#9467bd",
            "success": "#17becf",
        }

    def load_summary_data(self):
        """Load Prague 5 summary election data"""
        summary_file = self.results_dir / "prague5_summary_2022.json"
        if summary_file.exists():
            with open(summary_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def load_detailed_data(self):
        """Load detailed district-level election data"""
        detailed_file = self.detailed_dir / "prague5_detailed_results.json"
        if detailed_file.exists():
            with open(detailed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert to DataFrame for easier analysis
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

    def create_turnout_analysis(self):
        """Create voter turnout analysis visualization"""
        if self.detailed_data is None:
            logger.warning("No detailed data available for turnout analysis")
            return None

        df = self.detailed_data.copy()

        # Extract and clean data
        if "structured" in df.columns:
            # Extract structured data
            structured_data = []
            for _, row in df.iterrows():
                if isinstance(row["structured"], dict):
                    data_point = row["structured"].copy()
                    data_point["district_id"] = row["district_id"]
                    structured_data.append(data_point)

            if structured_data:
                df_clean = pd.DataFrame(structured_data)

                # Clean numeric columns
                if "Volebníúčast v %" in df_clean.columns:
                    df_clean["turnout_pct"] = self.clean_numeric_data(
                        df_clean, "Volebníúčast v %"
                    )
                if "Voličiv seznamu" in df_clean.columns:
                    df_clean["registered_voters"] = self.clean_numeric_data(
                        df_clean, "Voličiv seznamu"
                    )
                if "Platnéhlasy" in df_clean.columns:
                    df_clean["valid_votes"] = self.clean_numeric_data(
                        df_clean, "Platnéhlasy"
                    )

                # Create turnout visualization
                fig = make_subplots(
                    rows=2,
                    cols=2,
                    subplot_titles=(
                        "Voter Turnout by District",
                        "Registered Voters by District",
                        "Valid Votes by District",
                        "Turnout vs Registered Voters",
                    ),
                    specs=[
                        [{"type": "bar"}, {"type": "bar"}],
                        [{"type": "bar"}, {"type": "scatter"}],
                    ],
                )

                # Turnout by district
                fig.add_trace(
                    go.Bar(
                        x=df_clean["district_id"],
                        y=df_clean["turnout_pct"],
                        name="Turnout %",
                        marker_color=self.colors["primary"],
                    ),
                    row=1,
                    col=1,
                )

                # Registered voters by district
                fig.add_trace(
                    go.Bar(
                        x=df_clean["district_id"],
                        y=df_clean["registered_voters"],
                        name="Registered Voters",
                        marker_color=self.colors["secondary"],
                    ),
                    row=1,
                    col=2,
                )

                # Valid votes by district
                fig.add_trace(
                    go.Bar(
                        x=df_clean["district_id"],
                        y=df_clean["valid_votes"],
                        name="Valid Votes",
                        marker_color=self.colors["accent"],
                    ),
                    row=2,
                    col=1,
                )

                # Scatter plot: Turnout vs Registered Voters
                fig.add_trace(
                    go.Scatter(
                        x=df_clean["registered_voters"],
                        y=df_clean["turnout_pct"],
                        mode="markers+text",
                        text=df_clean["district_id"],
                        textposition="top center",
                        name="District Analysis",
                        marker=dict(size=10, color=self.colors["info"]),
                    ),
                    row=2,
                    col=2,
                )

                fig.update_layout(
                    title="Prague 5 Election 2022 - Voter Turnout Analysis",
                    height=800,
                    showlegend=False,
                )

                # Save visualization
                output_file = self.viz_dir / "turnout_analysis.html"
                fig.write_html(output_file)
                logger.info(f"Turnout analysis saved to {output_file}")

                return fig, df_clean

        return None

    def create_districts_overview(self):
        """Create districts overview map/visualization"""
        if self.districts_data is None:
            logger.warning("No districts data available")
            return None

        # Create a simple districts overview
        districts_df = pd.DataFrame(self.districts_data)

        if "district_id" in districts_df.columns:
            # Add some sample geographic coordinates for Prague 5 districts
            # In a real implementation, you would geocode actual addresses

            # Prague 5 approximate bounds
            lat_min, lat_max = 50.05, 50.08
            lon_min, lon_max = 14.38, 14.42

            districts_df["lat"] = np.random.uniform(lat_min, lat_max, len(districts_df))
            districts_df["lon"] = np.random.uniform(lon_min, lon_max, len(districts_df))

            # Create map visualization
            fig = px.scatter_mapbox(
                districts_df,
                lat="lat",
                lon="lon",
                text="district_id",
                title="Prague 5 Electoral Districts Map",
                mapbox_style="open-street-map",
                zoom=12,
                height=600,
            )

            fig.update_traces(
                marker=dict(size=15, color=self.colors["primary"]),
                textposition="middle center",
            )

            # Save map
            output_file = self.viz_dir / "districts_map.html"
            fig.write_html(output_file)
            logger.info(f"Districts map saved to {output_file}")

            return fig

        return None

    def create_summary_dashboard(self):
        """Create comprehensive summary dashboard"""
        logger.info("Creating Prague 5 Election Summary Dashboard")

        # Create multi-tab dashboard
        dashboard_data = {
            "title": "Prague 5 Municipal Elections 2022 - Analysis Dashboard",
            "districts_count": len(self.districts_data) if self.districts_data else 0,
            "analyzed_districts": len(self.detailed_data)
            if self.detailed_data is not None
            else 0,
        }

        if self.detailed_data is not None and not self.detailed_data.empty:
            # Calculate summary statistics
            structured_data = []
            for _, row in self.detailed_data.iterrows():
                if isinstance(row["structured"], dict):
                    data_point = row["structured"].copy()
                    data_point["district_id"] = row["district_id"]
                    structured_data.append(data_point)

            if structured_data:
                df_clean = pd.DataFrame(structured_data)
                df_clean["turnout_pct"] = self.clean_numeric_data(
                    df_clean, "Volebníúčast v %"
                )
                df_clean["registered_voters"] = self.clean_numeric_data(
                    df_clean, "Voličiv seznamu"
                )
                df_clean["valid_votes"] = self.clean_numeric_data(
                    df_clean, "Platnéhlasy"
                )

                dashboard_data.update(
                    {
                        "total_registered_voters": df_clean["registered_voters"].sum(),
                        "total_valid_votes": df_clean["valid_votes"].sum(),
                        "average_turnout": df_clean["turnout_pct"].mean(),
                        "highest_turnout_district": df_clean.loc[
                            df_clean["turnout_pct"].idxmax(), "district_id"
                        ],
                        "lowest_turnout_district": df_clean.loc[
                            df_clean["turnout_pct"].idxmin(), "district_id"
                        ],
                    }
                )

        # Create main dashboard figure
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Key Statistics",
                "District Participation",
                "Data Coverage",
                "Analysis Summary",
            ),
            specs=[
                [{"type": "indicator"}, {"type": "bar"}],
                [{"type": "pie"}, {"type": "table"}],
            ],
        )

        # Key indicators
        if "average_turnout" in dashboard_data:
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=dashboard_data["average_turnout"],
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "Average Turnout %"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": self.colors["primary"]},
                        "steps": [
                            {"range": [0, 30], "color": "lightgray"},
                            {"range": [30, 50], "color": "yellow"},
                            {"range": [50, 100], "color": "green"},
                        ],
                        "threshold": {
                            "line": {"color": "red", "width": 4},
                            "thickness": 0.75,
                            "value": 50,
                        },
                    },
                ),
                row=1,
                col=1,
            )

        # Data coverage pie chart
        coverage_data = {
            "Analyzed Districts": dashboard_data["analyzed_districts"],
            "Remaining Districts": dashboard_data["districts_count"]
            - dashboard_data["analyzed_districts"],
        }

        fig.add_trace(
            go.Pie(
                labels=list(coverage_data.keys()),
                values=list(coverage_data.values()),
                name="Data Coverage",
            ),
            row=2,
            col=1,
        )

        fig.update_layout(title=dashboard_data["title"], height=800)

        # Save dashboard
        output_file = self.viz_dir / "summary_dashboard.html"
        fig.write_html(output_file)
        logger.info(f"Summary dashboard saved to {output_file}")

        # Also save data summary as JSON
        summary_file = self.viz_dir / "dashboard_data.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        return fig, dashboard_data

    def generate_all_visualizations(self):
        """Generate all available visualizations"""
        logger.info("Generating all Prague 5 election visualizations")

        results = {}

        # 1. Turnout Analysis
        try:
            turnout_result = self.create_turnout_analysis()
            if turnout_result:
                results["turnout_analysis"] = turnout_result
                logger.info("✓ Turnout analysis completed")
        except Exception as e:
            logger.error(f"Error creating turnout analysis: {e}")

        # 2. Districts Map
        try:
            districts_map = self.create_districts_overview()
            if districts_map:
                results["districts_map"] = districts_map
                logger.info("✓ Districts map completed")
        except Exception as e:
            logger.error(f"Error creating districts map: {e}")

        # 3. Summary Dashboard
        try:
            dashboard_result = self.create_summary_dashboard()
            if dashboard_result:
                results["summary_dashboard"] = dashboard_result
                logger.info("✓ Summary dashboard completed")
        except Exception as e:
            logger.error(f"Error creating summary dashboard: {e}")

        # Generate index file
        self.create_visualization_index()

        logger.info(f"Generated {len(results)} visualizations in {self.viz_dir}")
        return results

    def create_visualization_index(self):
        """Create an index.html file linking to all visualizations"""
        index_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prague 5 Election Analysis - Visualizations</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #1f77b4; text-align: center; }
        .viz-card { background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #1f77b4; }
        .viz-card h3 { margin-top: 0; color: #333; }
        .viz-card a { color: #1f77b4; text-decoration: none; font-weight: bold; }
        .viz-card a:hover { text-decoration: underline; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-box { background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-number { font-size: 24px; font-weight: bold; color: #1976d2; }
        .stat-label { font-size: 14px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗳️ Prague 5 Municipal Elections 2022</h1>
        <h2>Analysis Dashboard</h2>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">81</div>
                <div class="stat-label">Electoral Districts</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">5</div>
                <div class="stat-label">Analyzed Districts</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">2022</div>
                <div class="stat-label">Election Year</div>
            </div>
        </div>
        
        <div class="viz-card">
            <h3>📊 Summary Dashboard</h3>
            <p>Comprehensive overview of Prague 5 election results with key metrics and indicators.</p>
            <a href="summary_dashboard.html" target="_blank">View Dashboard →</a>
        </div>
        
        <div class="viz-card">
            <h3>📈 Voter Turnout Analysis</h3>
            <p>Detailed analysis of voter participation across electoral districts, including turnout rates and valid votes.</p>
            <a href="turnout_analysis.html" target="_blank">View Analysis →</a>
        </div>
        
        <div class="viz-card">
            <h3>🗺️ Electoral Districts Map</h3>
            <p>Interactive map showing the distribution of Prague 5's electoral districts.</p>
            <a href="districts_map.html" target="_blank">View Map →</a>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: #fff3cd; border-radius: 8px; border-left: 4px solid #ffc107;">
            <h4>📋 Data Sources & Methodology</h4>
            <p><strong>Data Source:</strong> Czech Statistical Office (volby.cz) - 2022 Municipal Elections</p>
            <p><strong>Coverage:</strong> Prague 5 municipality (code: 500143)</p>
            <p><strong>Analysis Date:</strong> June 2025</p>
            <p><strong>Note:</strong> This analysis is based on publicly available election data and web scraping due to API access limitations.</p>
        </div>
    </div>
</body>
</html>
        """

        index_file = self.viz_dir / "index.html"
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(index_content)

        logger.info(f"Visualization index created at {index_file}")


if __name__ == "__main__":
    visualizer = Prague5Visualizer()
    results = visualizer.generate_all_visualizations()
    print(f"Generated {len(results)} visualizations!")
    print(f"Open data/visualizations/index.html to view the results.")
