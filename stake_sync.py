import os,requests,json

TOKEN=os.environ["STAKE_TOKEN"]

query="""
query BetHistory {
  user {
    sportBets(first: 20) {
      edges {
        node {
          id
          amount
          currency
          status
          cashoutMultiplier
          payout
          createdAt
          outcomes {
            odds
            outcome {
              name
              market {
                name
                fixture {
                  slug
                  data {
                    ... on SportFixtureDataMatch {
                      competitors {
                        name
                      }
                      startTime
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

r=requests.post(
    "https://api.stake.com/graphql",
    headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},
    json={"query":query}
)
print(r.status_code)
print(json.dumps(r.json(),indent=2)[:2000])
