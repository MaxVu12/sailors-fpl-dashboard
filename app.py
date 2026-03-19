import streamlit as st
import pandas as pd
import requests
from datetime import datetime 

# This keeps your app fast by not hitting the API on every single click
@st.cache_data(ttl=600) 
def get_data(url):
    return requests.get(url).json()

class FPLMoneyLeague:
    def __init__(self, league_id):
        self.league_id = league_id
        self.bootstrap_url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
        self.api_url = f"https://fantasy.premierleague.com/api/leagues-classic/{self.league_id}/standings/"
        
        # Your specific money mapping
        self.weekly_prize_mapping = {
            1: 45, 2: 35, 3: 25, 4: 20, 5: 15, 6: 10, 7: 0, 
            8: -5, 9: -10, 10: -10, 11: -15, 12: -20, 13: -25, 14: -30, 15: -35
        }

    def get_live_standings(self):
        data = get_data(self.api_url)
            
        # DEBUG: This helps us see the actual API response if it fails
        # st.write(data) 

        # Check if 'standings' exists in the response
        if 'standings' not in data:
            return pd.DataFrame({"Error": ["Could not find standings. Check if your League ID is a Classic League."]})
            
        if not data['standings'].get('results'):
            return pd.DataFrame({"Error": ["League hasn't started or no results found yet."]})
            
        # Extract and rename initial columns
        df = pd.json_normalize(data['standings']['results'])
        df = df[['player_name', 'entry_name', 'event_total', 'rank', 'total']]
        df.columns = ['Manager', 'Team Name', 'GW Points', 'Overall Rank', 'Total Points']
            
        # LOGIC: Sort by GW performance for the Weekly Prizes
        df = df.sort_values(by=['GW Points', 'Total Points'], ascending=[False, False])
            
        # Create the Weekly Rank based on this sort
        df['Weekly Rank'] = range(1, len(df) + 1)
            
        # Calculate Cash
        df['Weekly Cash'] = df['Weekly Rank'].map(self.weekly_prize_mapping).fillna(0)
            
        # Reorder columns as requested
        column_order = [
            'Weekly Rank', 'Manager', 'Team Name', 
            'GW Points', 'Weekly Cash', 'Overall Rank', 'Total Points'
        ]

        return df[column_order]

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sailors FPL", page_icon="⚽")
st.title("⚓ Sailors FPL Money League")

# Sidebar input for your league
league_id = st.sidebar.text_input("Enter FPL League ID", value="126694") # Put your real ID here

if st.button('Fetch Live Standings'):
    fpl = FPLMoneyLeague(league_id)
    with st.spinner('Calculating profits...'):
        df = fpl.get_live_standings()
        
        if "Error" in df.columns:
            st.error(df["Error"].iloc[0])
        else:
            # 1. Metric for the weekly winner
            top_row = df.iloc[0]
            st.metric(
                label="Current GW Leader", 
                value=top_row['Manager'], 
                delta=f"{top_row['GW Points']} pts"
            )
            
            st.write("### Weekly Breakdown")

            # 2. Custom function to fix the -$10 formatting
            def format_currency(val):
                if val < 0:
                    return f"-${abs(val):.0f}"
                return f"${val:.0f}"

            # 3. Apply Styling: Gradient, Formatting, and Hide Index
            styled_df = df.style.format({'Weekly Cash': format_currency}) \
                .background_gradient(subset=['Weekly Cash'], cmap='RdYlGn')

            # 4. Display the table
            st.dataframe(
                styled_df, 
                width='stretch',
                height=content, 
                hide_index=True)
            
            # Optional: Add a timestamp for that Toronto local feel
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')} ET")