import pandas as pd
import networkx as nx

class Tournament(object):
    '''A swiss tournament algorithm using minimum weight perfect matching'''
    def __init__(self):
        # player Data
        self.player_dict = {}
        # Completed fixture Data
        self.fixture_list = []
        # Pending fixture Data
        self.pending_fixture_list = []
        # Default seed
        self.default_seed = 0
        # Points for a win
        self.win_pts = 1
        #Points for a draw
        self.draw_pts = 0.5
        #Points for a bye
        self.bye_pts = 1
        # Matchday Count
        self.matchday = 0
        # Minimum Possible Pairings
        self.min_pairings = 20
        # Tiebreaker
        self.tiebreaker = 'sonneborn-berger'
        # Whether to consider home and away
        self.home_away = True
        # Maximum number of meetings
        self.max_meetings = 1        
    
    def add_player(self, name, **kwargs):
        '''Add a player to the tournament'''
        self.player_dict[name] = {'seed': self.default_seed,
                                 'points': 0,
                                 'opponents': [],
                                'home_away': [],
                                'home_away_restriction': None,
                                'home_away_gap': 0,
                                 'byes': 0, 
                                'sonneborn-berger': 0}
        
        self.player_dict[name].update(kwargs)
        
    def players_df(self):
        df = pd.DataFrame(self.player_dict).transpose().sample(frac = 1).sort_values(by = ['points','seed'], ascending = [False,True]).reset_index(names = 'name')
        return df
    
    # Pair all players with no extra restrictions
    def create_fixtures(self):
        '''Creates a set of fixtures for the next round'''
        self.matchday += 1
        
        if self.home_away:
        # Update home/away restrictions
            for player in self.player_dict:
                self.home_away_restriction(player)
            
        players_df = self.players_df()
    
        # Check whether a player needs to be given a bye
        byeNeeded = (len(players_df) % 2 == 1)
        
        # Create a network graph
        G = nx.Graph()
        
        # Parameters for creating possible pairings
        reach = max(max(players_df.points.value_counts()), self.min_pairings, self.matchday)
        step = max(int(reach/self.min_pairings), 1)
        
        # Add edges for each pairing of players
        for idx, data1 in players_df.iterrows():
            player1 = data1['name']
            options = players_df[idx + 1 : idx + reach : step]
            
            for idx2, data2 in options.iterrows():
                player2 = data2['name']
                
                ptsGap = abs(data1['points'] - data2['points'])
                seedGap = abs(data1['seed'] - data2['seed'])
                
                if self.home_away:
                    # Check home/away restrictions
                    home_away_penalty = 0
                    restriction1 = data1['home_away_restriction']
                    restriction2 = data2['home_away_restriction']
                    if (restriction1 == restriction2) & (restriction1 != None):
                        home_player1 = None
                        home_away_penalty += 1
                    elif (restriction1 == 'home only') | (restriction2 == 'away only'):
                        home_player1 = player1
                    elif (restriction2 == 'home only') | (restriction1 == 'away only'):
                        home_player1 = player2
                    else:
                        home_player1 = None

                    # Check Previous Matches
                    previous_matches = max(data1['opponents'].count(player2) + 1 - self.max_meetings, 0)

                    previous_matches_ha = [data1['home_away'][i] for i, x in enumerate(data1['opponents']) if x == player2]
                    if previous_matches_ha.count('home') > previous_matches_ha.count('away'):
                        home_player2 = player2
                    elif previous_matches_ha.count('home') < previous_matches_ha.count('away'):
                        home_player2 = player1
                    else:
                        home_player2 = None

                    home_player = None
                    if (home_player1 == home_player2) | (home_player1 == None) | (home_player2 == None):
                        for home_player_decider in [home_player1, home_player2]:
                            if home_player_decider != None:
                                home_player = home_player_decider
                        if home_player == None:
                            gap = data1['home_away_gap'] - data2['home_away_gap']
                            if gap < 0:
                                home_player = player1
                            elif gap > 0:
                                home_player = player2
                    else:
                        home_away_penalty += 1
                        home_player = player1
                else:
                    home_player = player1
                
                # weights are determined by number of previous matches, 
                # home/away restrictions, points gap and seed gap
                weight = previous_matches * 1000 + home_away_penalty * 100 + ptsGap - seedGap/1000
                
                G.add_edge(player1, player2, weight = weight, home = home_player)
            
            # Calculate bye weights if necessary
            if byeNeeded & (len(players_df) - idx < 101):
                pts = data1['points']
                seed = data1['seed']
                byes = data1['byes']

                weight = byes*1000 + pts - seed/1000
                G.add_edge(player1,'bye', weight = weight)
            
        # Conduct minumum weight matching
        fixtures = nx.algorithms.matching.min_weight_matching(G)
        
        # Add opponent to each player, and bye count for the player with a bye
        for fixture in fixtures:
            if 'bye' in fixture:
                for player in fixture:
                    if player != 'bye':
                        self.player_dict[player]['byes'] += 1
                        self.player_dict[player]['points'] += self.bye_pts
            else:
                player1, player2 = fixture[0], fixture[1]
                self.player_dict[player1]['opponents'].append(player2)
                self.player_dict[player2]['opponents'].append(player1)
                
                if self.home_away:
                    # Deciding which player plays home
                    if G[player1][player2]['home'] == player2:
                        final_fixture = (fixture[1], fixture[0])
                        self.player_dict[player2]['home_away'].append('home')
                        self.player_dict[player1]['home_away'].append('away')
                    else:
                        final_fixture = fixture
                        self.player_dict[player1]['home_away'].append('home')
                        self.player_dict[player2]['home_away'].append('away')
                else:
                    final_fixture = fixture
                
                self.pending_fixture_list.append((final_fixture[0], final_fixture[1], self.matchday))
        
    
    def report_result(self, result, more = {}):
        '''Adds a result to the tournament'''
        # Result format: {player1: score1, player2: score2}
        
        players = list(result.keys())
        totals = list(result.values())
        
        # Remove entry in pending fixture list
        for fixture in self.pending_fixture_list:
            if (players[0] in fixture) & (players[1] in fixture):
                matchday = fixture[2]
                self.pending_fixture_list.remove(fixture)
        
        # Interpret result and add points
        if totals[0] > totals[1]:
            res =  players[0]
            self.player_dict[players[0]]['points'] += self.win_pts
        elif totals[0] == totals[1]:
            res = 'draw'
            for player in players:
                self.player_dict[player]['points'] += self.draw_pts
        else:
            res = players[1]
            self.player_dict[players[1]]['points'] += self.win_pts
        
        # Store fixture result in fixture list
        result_dict = {'Home': players[0], 
                       'score1': totals[0], 
                       'score2': totals[1], 
                       'Away': players[1], 
                       'Result': res, 
                       'Matchday': matchday}
        result_dict.update(more)
        self.fixture_list.append(result_dict)
        
    def fixtures_df(self, player = ''):
        '''Generates a pandas DataFrame of all fixtures, or all fixtures played by one player'''
        df = pd.DataFrame(self.fixture_list)
        if player != '':
            df = df[(df.Home == player) | (df.Away == player)]
        return df
    
    def league_table(self):
        '''Generates a league table'''
        self.sonneborn_berger()
        df = pd.DataFrame(self.player_dict).transpose()[['seed','sonneborn-berger','points']].sort_values(['points','sonneborn-berger','seed'], ascending = [False,False,True]).reset_index(names = 'player')
        return df
    
    def sonneborn_berger(self):
        for player in self.player_dict:
            tiebreaker = 0
            fixture_df = self.fixtures_df()
            results = fixture_df[(fixture_df.Home == player) | (fixture_df.Away == player)].reset_index(drop = True).Result
            opponents = self.player_dict[player]['opponents']

            for opponent, result in zip(opponents, results):
                opp_points = self.player_dict[opponent]['points']

                if result == player:
                    tiebreaker += self.win_pts * opp_points
                elif result == 'draw':
                    tiebreaker += self.draw_pts * opp_points
            
            self.player_dict[player]['sonneborn-berger'] = tiebreaker
            
    def home_away_restriction(self, player):
        data = self.player_dict[player]
        home_away_list = data['home_away']
        home_away_gap = home_away_list.count('home') - home_away_list.count('away')
        self.player_dict[player]['home_away_gap'] = home_away_gap
        restriction = None
        
        # Checks for previous 2 and 4 matches
        for check in ['home','away']:
            last2_check = (home_away_list[-2:].count(check) == 0) & (len(home_away_list) > 1)
            last4_check = (home_away_list[-4:].count(check) <= 1) & (len(home_away_list) > 3)
            if last2_check | last4_check:
                restriction = check + ' only'
        
        if restriction == None:
            # Check for overall home and away matches
            if home_away_gap <= -2:
                restriction = 'home only'
            elif home_away_gap >= 2:
                restriction = 'away only'
            else:
                restriction = None

        self.player_dict[player]['home_away_restriction'] = restriction