import streamlit as st
import pandas as pd
import requests

# 1. Page Configuration
st.set_page_config(page_title="FPL Money League", page_icon="⚽")

# 2. Your Logic (The "Engine")
def get_fpl_data(league_id):
    """
    This replaces your Colab logic. 
    For now, we'll use a placeholder to show how it displays.
    """
    # In reality, you'd use: requests.get(f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/")
    mock_data = {
        "Manager": ["Alice", "Bob", "Charlie", "Dave"],
        "GW_Points": [65, 58, 72, 45],
        "Total_Points": [1200, 1150, 1180, 1100],
        "Weekly_Result": [10.00, -5.00, 20.00, -25.00] # Your calculated $
    }
    return pd.DataFrame(mock_data)

# 3. The Dashboard UI
st.title("🏆 FPL Money League Dashboard")
st.subheader("Weekly Earnings & Standings")

# Sidebar for inputs (keeps the main page clean)
league_id = st.sidebar.text_input("Enter FPL League ID", value="123456")

if st.button('Refresh Data'):
    with st.spinner('Calculating profits...'):
        # Call your function
        df = get_fpl_data(league_id)
        
        # Display Top Performer Metric
        top_manager = df.iloc[df['GW_Points'].idxmax()]
        st.metric(label="Weekly High Scorer", value=top_manager['Manager'], delta=f"{top_manager['GW_Points']} pts")

        # Display the main table
        st.write("### Current Week Breakdown")
        st.dataframe(df.style.highlight_max(axis=0, subset=['Weekly_Result'], color='lightgreen'))

        # Add a simple chart for visual flair
        st.bar_chart(data=df, x="Manager", y="Weekly_Result")

else:
    st.info("Click the button above to pull the latest data from the FPL API.")

st.divider()
st.caption("Built with Streamlit • Managed by League Admin")
