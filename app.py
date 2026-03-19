import streamlit as st
import pandas as pd
import requests
from datetime import datetime 
import pytz

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

    def get_gameweek_info(self):
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        data = requests.get(url).json()
        
        events = data['events']
        current_gw = next((e for e in events if e['is_current']), events[0])
        next_gw = next((e for e in events if e['is_next']), None)
        
        deadline_local = "N/A"
        
        if next_gw:
            # 1. Parse FPL UTC time
            utc_time = datetime.strptime(next_gw['deadline_time'], '%Y-%m-%dT%H:%M:%SZ')
            # 2. Add UTC timezone info
            utc_time = utc_time.replace(tzinfo=pytz.utc)
            # 3. Format it with the timezone name (e.g., UTC)
            deadline_local = utc_time.strftime('%b %d, %I:%M %p %Z')
                
        return current_gw['id'], deadline_local  

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sailors FPL", page_icon="⚽")
st.title("⚓ Sailors FPL Money League")

# 1. Initialize class and fetch GW info immediately
fpl = FPLMoneyLeague("126694")

try:
    current_gw, deadline_str = fpl.get_gameweek_info()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current Gameweek", f"GW {current_gw}")
    with col2:
        # This will show "Mar 21, 11:00 AM UTC" 
        # which is clear for everyone to convert mentally
        st.metric("Next Deadline", deadline_str)
    
    st.info("💡 Tip: FPL deadlines are shown in UTC. Toronto is UTC-4, Hanoi is UTC+7.")
    st.divider()
except Exception as e:
    st.warning("Could not fetch current Gameweek status.")

# 2. The Button and Table Logic
if st.button('Fetch Live Standings'):
    with st.spinner('Calculating profits...'):
        df = fpl.get_live_standings()
        
        if "Error" in df.columns:
            st.error(df["Error"].iloc[0])
        else:
            # Metric for the weekly winner
            top_row = df.iloc[0]
            st.metric(
                label="Current GW Leader", 
                value=top_row['Manager'], 
                delta=f"{top_row['GW Points']} pts"
            )
            
            st.write("### Weekly Breakdown")

            # Custom function to fix the -$10 formatting
            def format_currency(val):
                if val < 0:
                    return f"-${abs(val):.0f}"
                return f"${val:.0f}"

            # Apply Styling
            styled_df = df.style.format({'Weekly Cash': format_currency}) \
                .background_gradient(subset=['Weekly Cash'], cmap='RdYlGn')

            # Display the table
            st.dataframe(
                styled_df, 
                width='stretch',
                height='content', 
                hide_index=True
            )
            
            # Timestamp
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')} ET")