import pandas as pd
import requests
import pytz
from datetime import datetime 

class FPLMoneyLeague:

    def __init__(self, league_id):
        self.league_id = league_id
        self.bootstrap_url = f"https://fantasy.premierleague.com/api/bootstrap-static/"
        self.api_url = f"https://fantasy.premierleague.com/api/leagues-classic/{self.league_id}/standings/"
    
        # Your specific money mapping
        self.weekly_prize_mapping = {
            1: 45, 
            2: 35, 
            3: 25, 
            4: 20, 
            5: 15, 
            6: 10, 
            7: 0, 
            8: -5, 
            9: -10, 
            10: -10, 
            11: -15, 
            12: -20, 
            13: -25, 
            14: -30, 
            15: -35
        }

    def _get_data(self, url):
        try:
            response = requests.get(url, timeout=10)
            return response.json()
        except Exception as e:
            print(f"API Error: {e}")
            return {}

    def get_league_managers(self):
        """Fetches and sorts managers by Entry ID (Lowest first)."""
        data = self._get_data(self.api_url)
        if not data or 'standings' not in data:
            return {}
        
        # 1. Get the raw list
        raw_results = data['standings']['results']
        
        # 2. Sort the list by 'entry' ID ascending
        sorted_results = sorted(raw_results, key=lambda x: x['entry'])
        
        # 3. Create the dict (Python 3.7+ preserves insertion order)
        return {
            f"{r['player_name']} ({r['entry_name']})": r['entry'] 
            for r in sorted_results
        }
    
    def get_gameweek_info(self):
        data = requests.get(self.bootstrap_url).json()
            
        events = data['events']
        current_gw = next((e for e in events if e['is_current']), events[0])
        next_gw = next((e for e in events if e['is_next']), None)
            
        deadline_to = "N/A"
        deadline_vn = "N/A"
            
        if next_gw:
            utc_time = datetime.strptime(next_gw['deadline_time'], '%Y-%m-%dT%H:%M:%SZ')
            utc_time = pytz.utc.localize(utc_time)
                    
            # Format for Toronto (Force 'EDT/EST' label)
            to_time = utc_time.astimezone(pytz.timezone('America/Toronto'))
            deadline_to = to_time.strftime('%b %d, %I:%M %p') + " EDT"
                    
            # Format for Hanoi (Force 'ICT' label)
            vn_time = utc_time.astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
            deadline_vn = vn_time.strftime('%b %d, %I:%M %p') + " ICT"
                    
        return current_gw['id'], deadline_to, deadline_vn

    def get_managers(self):
        """Returns a list of dictionaries containing basic manager info."""
        data = self._get_data(self.api_url)
        
        if 'standings' not in data or not data['standings'].get('results'):
            return []
            
        managers = []
        for entry in data['standings']['results']:
            managers.append({
                'Team ID': entry['entry'],
                'Manager': entry['player_name'],
                'Team Name': entry['entry_name']
            })
        return managers
    
    def calculate_team_gw_point(self, team_id, gw):
        """Fetches the specific stats for a manager for a given GW."""
        url = f"https://fantasy.premierleague.com/api/entry/{team_id}/history/"
        data = self._get_data(url)
        
        # 'current' contains the list of all completed/active gameweeks
        if not data or 'current' not in data:
            return None
            
        # Find the specific week in the history list
        for week in data['current']:
            if week['event'] == gw:
                return {
                    'GW Points': week['points'],
                    'Hits': int(week['event_transfers_cost']) * -1,
                    'Bench': int(week['points_on_bench']),
                    'Total': week['total_points']
                }
        return None
    
    def _build_standings_table(self, manager_list, gw):
        """Processes raw manager data into the final Sailors FPL DataFrame."""
        df = pd.DataFrame(manager_list)
        
        if df.empty:
            return pd.DataFrame({"Error": ["No data available"]})

        # 1. Calculate League Rank based on Total Points
        # We sort by Total (Descending) then assign a rank
        df = df.sort_values(by='Total', ascending=False)
        df['League Rank'] = range(1, len(df) + 1)

        # 2. Tiebreaker Logic
        df['is_tied'] = df.duplicated(subset=['GW Points', 'Hits', 'Bench'], keep=False)

        def resolve_deadlock(row, target_gw):
            if row['is_tied']:
                return self.get_last_two_gw_points(row['Team ID'], target_gw)
            return 0
        
        df['Last 2 GW'] = df.apply(lambda x: resolve_deadlock(x, gw), axis=1)

        # 3. Sort by League Rules
        df = df.sort_values(
            by=['GW Points', 'Hits', 'Bench', 'Last 2 GW'], 
            ascending=[False, False, False, False]
        )
        
        # 4. Rank and Cash
        df['GW Rank'] = range(1, len(df) + 1)
        df['GW Cash'] = df['GW Rank'].map(self.weekly_prize_mapping).fillna(0)
        
        # 5. Consistent Column Order
        column_order = [
            'GW Rank', 'Manager', 'Team Name', 'GW Points', 
            'GW Cash', 'Hits', 'Bench', 'League Rank', 'Total'
        ]
        if (df['Last 2 GW'] > 0).any():
            column_order.append('Last 2 GW')

        return df[column_order]

    def get_live_standing(self):
        """Exclusively pulls the current active Gameweek data."""
        current_gw, _, _ = self.get_gameweek_info()
        
        # Get the list of managers from the league API
        league_data = self._get_data(self.api_url)
        standings_results = league_data['standings']['results']
        
        processed_managers = []
        for entry in standings_results:
            stats = self.calculate_team_gw_point(entry['entry'], current_gw)
            if stats:
                # Combine the basic info (names) with the deep stats
                stats.update({
                    'Team ID': entry['entry'],
                    'Manager': entry['player_name'],
                    'Team Name': entry['entry_name']
                })
                processed_managers.append(stats)
                
        return self._build_standings_table(processed_managers, current_gw)
    
    def get_historical_standing(self, gw):
        """
        Fetches historical standings by first getting the manager list 
        and then pulling specific GW stats for each.
        """
        # 1. Get the list of everyone currently in the league
        managers = self.get_managers()
        
        if not managers:
            return pd.DataFrame({"Error": ["No managers found in league."]})
            
        processed_managers = []
        
        # 2. Loop through each manager to get their TRUE stats for that GW
        for manager in managers:
            # Use your core function to get points, hits, and bench
            stats = self.calculate_team_gw_point(manager['Team ID'], gw)
            
            if stats:
                # Merge the 'Who' (names) with the 'How much' (stats)
                stats.update({
                    'Manager': manager['Manager'],
                    'Team Name': manager['Team Name'],
                    'Team ID': manager['Team ID']
                })
                processed_managers.append(stats)
                
        # 3. Use your shared formatter to handle tie-breakers, sorting, and cash
        return self._build_standings_table(processed_managers, gw)

    def get_last_two_gw_points(self, team_id, current_gw):
        """Fetches points for the previous two gameweeks with error handling."""
        # 1. Handle the start of the season
        if current_gw <= 1:
            return 0

        total_past_points = 0
        # Look back at the last 2 weeks (or just 1 if we are in GW2)
        weeks_to_check = [current_gw - 1, current_gw - 2]
        
        for gw in weeks_to_check:
            if gw < 1:
                continue
                
            url = f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/"
            
            try:
                response = requests.get(url, timeout=5) # 5s timeout so it doesn't hang
                if response.status_code == 200:
                    data = response.json()
                    # Safely navigate the JSON tree
                    points = data.get('entry_history', {}).get('points', 0)
                    total_past_points += points
                else:
                    # If API fails for one week, we just count it as 0
                    continue
            except Exception as e:
                # Logs the error to your terminal but keeps the app running
                print(f"Error fetching GW{gw} for {team_id}: {e}")
                continue
                
        return total_past_points

    def get_gw_live_data(self, gw):
        """
        Fetches live points and merges them with player positions 
        to prevent KeyErrors during simulation.
        """
        # 1. Get the "Who is what position" map (Bootstrap Static)
        static_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        static_data = self._get_data(static_url)
        pos_map = {el['id']: el['element_type'] for el in static_data['elements']}
        
        # 2. Get the "How did they do this week" stats (Live)
        live_url = f"https://fantasy.premierleague.com/api/event/{gw}/live/"
        live_data = self._get_data(live_url)
        
        # 3. Merge them into one clean dictionary
        return {
            el['id']: {
                'points': el['stats']['total_points'],
                'minutes': el['stats']['minutes'],
                'position': pos_map.get(el['id']) # This fixes the KeyError!
            } for el in live_data['elements']
        }
    
    def simulate_score(self, picks, live_data):
        """Calculates score with Captaincy and 3-Def-Min Autosub rules."""
        starters = [p for p in picks if p['position'] <= 11]
        bench = sorted([p for p in picks if p['position'] > 11], key=lambda x: x['position'])
        
        # 1. Captaincy & Vice-Captaincy
        cap = next(p for p in picks if p['is_captain'])
        vc = next(p for p in picks if p['is_vice_captain'])
        
        # Check if original captain played any minutes
        active_id = cap['element'] if live_data[cap['element']]['minutes'] > 0 else vc['element']
        
        # 2. Base Points for Starters who actually played
        playing_starters = [p for p in starters if live_data[p['element']]['minutes'] > 0]
        points = sum(live_data[p['element']]['points'] for p in playing_starters)
        
        # Add the double points for whoever ended up with the armband
        points += live_data[active_id]['points'] 

        # 3. Autosub Logic
        missing = [p for p in starters if live_data[p['element']]['minutes'] == 0]
        available_bench = [p for p in bench if live_data[p['element']]['minutes'] > 0]
        
        # Count how many defenders are currently in the playing XI
        def_count = sum(1 for p in playing_starters if live_data[p['element']]['position'] == 2)

        for m in missing:
            m_pos = live_data[m['element']]['position']
            
            for b in available_bench:
                b_id = b['element']
                b_pos = live_data[b_id]['position']
                
                can_sub = False
                
                # RULE: Keeper for Keeper
                if m_pos == 1:
                    if b_pos == 1: 
                        can_sub = True
                
                # RULE: Outfield for Outfield
                else:
                    if b_pos != 1:
                        # If we are losing a defender and already at the 3-DEF minimum, 
                        # we MUST sub in another defender.
                        if m_pos == 2 and def_count < 3:
                            if b_pos == 2: 
                                can_sub = True
                        else:
                            # Otherwise, any outfield player can come on
                            can_sub = True
                
                if can_sub:
                    points += live_data[b_id]['points']
                    if b_pos == 2: 
                        def_count += 1
                    available_bench.remove(b) # This player is now used
                    break # Move to the next missing starter
                    
        return points