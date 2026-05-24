import streamlit as st
import asyncio
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from io import StringIO
import contextlib

# Import workspace modules
from config import get_city, list_cities, OLX_CATEGORIES, QUIKR_CATEGORIES
from scrapers.olx_scraper import scrape_olx
from scrapers.quikr_scraper import scrape_quikr
from analyzer import compute_liquidity_scores, aggregate_cross_platform, tier_label

# Set page config
st.set_page_config(
    page_title="Vingo · C2C Category Liquidity Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom premium styling via CSS
st.markdown(
    """
    <style>
    /* Dark theme customizations */
    .stApp {
        background: #0f0f23;
        color: #e2e8f0;
    }
    .main-title {
        font-family: 'DM Sans', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        color: #818cf8;
        margin-bottom: 0.25rem;
        background: linear-gradient(90deg, #818cf8, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #1e1b4b;
        border: 1px solid #4f46e555;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s, border-color 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #818cf8;
    }
    .metric-rank {
        font-size: 0.85rem;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 1.25rem;
        font-weight: 800;
        color: #c7d2fe;
    }
    .metric-score {
        font-size: 2rem;
        font-weight: 900;
        color: #34d399;
        margin: 0.5rem 0;
    }
    .metric-listings {
        font-size: 0.8rem;
        color: #94a3b8;
    }
    .tier-badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-top: 0.5rem;
    }
    .tier-badge-1 { background: #064e3b; color: #34d399; }
    .tier-badge-2 { background: #78350f; color: #fbbf24; }
    .tier-badge-3 { background: #7f1d1d; color: #f87171; }
    .tier-badge-4 { background: #1e293b; color: #94a3b8; }
    
    /* Log console style */
    .log-console {
        background: #02020a;
        color: #38bdf8;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.85rem;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #1e293b;
        max-height: 250px;
        overflow-y: auto;
        margin-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar UI
st.sidebar.markdown(
    "<h2 style='color:#818cf8; font-weight:800; font-size:1.6rem;'>⚡ vingo</h2>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("<p style='color:#94a3b8; font-size:0.85rem; margin-top:-0.5rem;'>C2C Category Liquidity Research</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Inputs
cities = list_cities()
city_choice = st.sidebar.selectbox("Select Target City", options=cities, index=0, format_func=lambda x: x.title())

sources = st.sidebar.multiselect("Scraping Sources", options=["olx", "quikr"], default=["olx", "quikr"])

scan_mode = st.sidebar.radio(
    "Scan Scope",
    options=["Full Category Scan (Comprehensive)", "Quick Validation Scan (Fast)"],
    index=0
)

no_cache = st.sidebar.checkbox("Force Fresh Scrape (Ignore Checkpoint)", value=False)

st.sidebar.markdown("---")

# Run campaign button
start_btn = st.sidebar.button("🚀 Launch Scraping Campaign", use_container_width=True)

# Main Body
st.markdown("<h1 class='main-title'>vingo — Category Liquidity Dashboard</h1>", unsafe_allow_html=True)
st.markdown(
    f"<p class='subtitle'>Real-time C2C marketplace analysis & launch prioritizer  ·  <b>City: {city_choice.title()}</b></p>",
    unsafe_allow_html=True
)

# Set city config
city_config = get_city(city_choice)

# Helper to capture async logs to standard output
class RedirectText:
    def __init__(self):
        self.buffer = StringIO()

    def write(self, val):
        self.buffer.write(val)

    def getvalue(self):
        return self.buffer.getvalue()

async def run_scrape_campaign(status_log):
    quick = (scan_mode == "Quick Validation Scan (Fast)")
    resume = not no_cache

    all_records = []
    
    # Run OLX Scraper
    if "olx" in sources:
        status_log.markdown("⏱ **Starting OLX scraping campaign...**")
        try:
            olx_data = await scrape_olx(
                city=city_config,
                resume=resume,
                quick=quick,
            )
            all_records.extend(olx_data)
        except Exception as e:
            status_log.markdown(f"❌ OLX Scrape Error: {e}")

    # Run Quikr Scraper
    if "quikr" in sources:
        status_log.markdown("⏱ **Starting Quikr scraping campaign...**")
        try:
            quikr_data = await scrape_quikr(
                city=city_config,
                quick=quick,
            )
            all_records.extend(quikr_data)
        except Exception as e:
            status_log.markdown(f"❌ Quikr Scrape Error: {e}")

    return all_records

# If button is pressed, run scraping
if start_btn:
    if not sources:
        st.warning("⚠️ Please select at least one source (OLX or Quikr) in the sidebar!")
    else:
        # Session state to store data
        st.session_state["scraped"] = True
        
        # UI status block
        status_header = st.empty()
        status_log = st.empty()
        
        # Display scraping start
        status_header.markdown(f"### ⚡ Running campaign for {city_config.display_name}...")
        
        # Run with async capturing
        log_stream = StringIO()
        with contextlib.redirect_stdout(log_stream):
            # We run the async loop
            with st.spinner("Scraping classifieds categories..."):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                records = loop.run_until_complete(run_scrape_campaign(status_log))
                loop.close()
        
        # Display logs
        logs = log_stream.getvalue()
        st.markdown("### 📋 Campaign Logs")
        st.markdown(f"<div class='log-console'>{logs.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
        
        if records:
            # Save results in session state
            st.session_state["raw_records"] = records
            status_header.success(f"✓ Campaign successfully completed! Scraped {len(records)} categories.")
            status_log.empty()
        else:
            st.error("❌ No data collected. Please verify network connection.")

# Retrieve data if scraped or display last run cached report
has_data = "raw_records" in st.session_state

if has_data:
    records = st.session_state["raw_records"]
    
    # Process analyzed scores
    per_source_df = compute_liquidity_scores(records)
    combined_df = aggregate_cross_platform(per_source_df)
    
    st.markdown("## 📊 Liquidity Score Insights")
    
    # Top launch candidates cards
    st.markdown("### 🌟 Recommended launch categories (Top 4)")
    cols = st.columns(4)
    
    top_candidates = combined_df.head(4).reset_index(drop=True)
    
    for i in range(4):
        with cols[i]:
            if i < len(top_candidates):
                row = top_candidates.iloc[i]
                score = row["avg_liquidity_score"]
                tier = tier_label(score)
                tier_cls = "1" if "TIER 1" in tier else ("2" if "TIER 2" in tier else ("3" if "TIER 3" in tier else "4"))
                
                st.markdown(
                    f"""
                    <div class='metric-card'>
                        <div class='metric-rank'>Launch Priority #{i+1}</div>
                        <div class='metric-value'>{row['category']}</div>
                        <div class='metric-score'>{score:.0f}</div>
                        <div class='metric-listings'>{row['total_listings']:,} active ads</div>
                        <span class='tier-badge tier-badge-{tier_cls}'>{tier.split(' — ')[0]}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div class='metric-card'>
                        <div class='metric-rank'>-</div>
                        <div class='metric-value'>No Category</div>
                        <div class='metric-score'>-</div>
                        <div class='metric-listings'>0 active ads</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
    st.markdown("---")
    
    # Tabs layout
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔗 Unified Cross-Platform Ranking", 
        "📈 Interactive Charts", 
        "📂 Source-specific Breakdown",
        "💾 Data Export"
    ])
    
    with tab1:
        st.markdown("#### Combined Cross-Platform Market Research")
        # Format unified dataframe for premium display
        unified_display = combined_df.copy()
        
        # Sort and reset rank
        unified_display = unified_display.reset_index()
        unified_display = unified_display.rename(columns={"rank": "Rank", "category": "Category", "sources": "Available Sources", "avg_liquidity_score": "Liquidity Score", "total_listings": "Total Listings", "max_freshness_7d": "Freshness (7d)", "max_freshness_24h": "Freshness (24h)"})
        
        # Display styled dataframe
        st.dataframe(
            unified_display[["Rank", "Category", "Available Sources", "Liquidity Score", "Total Listings", "Freshness (7d)", "Freshness (24h)"]],
            use_container_width=True,
            column_config={
                "Liquidity Score": st.column_config.ProgressColumn(
                    "Liquidity Score",
                    help="Aggregate launch readiness score (0-100)",
                    format="%.1f",
                    min_value=0,
                    max_value=100
                ),
                "Total Listings": st.column_config.NumberColumn(format="%d"),
                "Freshness (7d)": st.column_config.NumberColumn(format="%.0f%%"),
                "Freshness (24h)": st.column_config.NumberColumn(format="%.0f%%"),
            },
            hide_index=True
        )
        
    with tab2:
        st.markdown("#### Category Liquidity Performance")
        
        chart_data = combined_df.copy().sort_values("avg_liquidity_score", ascending=True)
        st.bar_chart(
            chart_data,
            x="category",
            y="avg_liquidity_score",
            color="#818cf8",
            use_container_width=True
        )
        
    with tab3:
        st.markdown("#### Platform-Specific Breakdown (OLX vs Quikr)")
        
        olx_df = per_source_df[per_source_df["source"] == "OLX"].copy().reset_index(drop=True)
        quikr_df = per_source_df[per_source_df["source"] == "Quikr"].copy().reset_index(drop=True)
        
        olx_tab, quikr_tab = st.tabs(["🟣 OLX Platform", "🔵 Quikr Platform"])
        
        with olx_tab:
            st.dataframe(
                olx_df[["category", "total_listings", "freshness_7d_pct", "freshness_24h_pct", "liquidity_score", "error"]],
                use_container_width=True,
                column_config={
                    "total_listings": st.column_config.NumberColumn("Total Listings", format="%d"),
                    "freshness_7d_pct": st.column_config.NumberColumn("Freshness (7d)", format="%.1f%%"),
                    "freshness_24h_pct": st.column_config.NumberColumn("Freshness (24h)", format="%.1f%%"),
                    "liquidity_score": st.column_config.ProgressColumn("Liquidity Score", min_value=0, max_value=100, format="%.1f"),
                },
                hide_index=True
            )
            
        with quikr_tab:
            st.dataframe(
                quikr_df[["category", "total_listings", "freshness_7d_pct", "freshness_24h_pct", "liquidity_score", "error"]],
                use_container_width=True,
                column_config={
                    "total_listings": st.column_config.NumberColumn("Total Listings", format="%d"),
                    "freshness_7d_pct": st.column_config.NumberColumn("Freshness (7d)", format="%.1f%%"),
                    "freshness_24h_pct": st.column_config.NumberColumn("Freshness (24h)", format="%.1f%%"),
                    "liquidity_score": st.column_config.ProgressColumn("Liquidity Score", min_value=0, max_value=100, format="%.1f"),
                },
                hide_index=True
            )
            
    with tab4:
        st.markdown("#### Download Scrape Campaign Data")
        
        # Save files to JSON and CSV formats
        combined_csv = combined_df.to_csv(index=False)
        per_source_csv = per_source_df.to_csv(index=False)
        raw_json_str = json.dumps(records, indent=2, default=str)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="📥 Download Unified Ranking (CSV)",
                data=combined_csv,
                file_name=f"vingo_combined_{city_config.name}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col2:
            st.download_button(
                label="📥 Download Per-source Breakdown (CSV)",
                data=per_source_csv,
                file_name=f"vingo_sources_{city_config.name}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col3:
            st.download_button(
                label="📥 Download Raw JSON Data",
                data=raw_json_str,
                file_name=f"vingo_raw_{city_config.name}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )

else:
    # Empty state placeholder
    st.info("💡 **Welcome to the Vingo Liquidity Tool!** To get started, configure your target Indian city and click the **🚀 Launch Scraping Campaign** button in the sidebar to fetch C2C listings data.")
    
    # Display information panel
    st.markdown(
        """
        <div style='background: #1e1b4b; border: 1px solid #4f46e555; border-radius: 12px; padding: 1.5rem; margin-top: 2rem;'>
            <h3 style='color: #818cf8; margin-top: 0;'>What is a Liquidity Score?</h3>
            <p style='color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;'>
                In a consumer-to-consumer (C2C) marketplace like eBay, <b>liquidity</b> represents the speed and ease with which buyers and sellers can complete transactions.
                Higher liquidity means a healthier, more self-sustaining market flywheel.
            </p>
            <p style='color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;'>
                Our tool scans OLX and Quikr's localized feeds in real time to calculate a score from <b>0 to 100</b> per category based on:
            </p>
            <ul style='color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; margin-left: 1.5rem;'>
                <li><b>Listing Volume (40%)</b>: Total number of active classified advertisements (indicates market size).</li>
                <li><b>Freshness 7-Day (40%)</b>: Proportion of ads created within the last week (indicates supply velocity).</li>
                <li><b>Freshness 24-Hour (20%)</b>: Proportion of ads created in the last 24 hours (indicates immediate transaction activity).</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )
