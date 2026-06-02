import os,requests

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
          payout
          createdAt
        }
      }
    }
  }
}
"""

r=requests.post(
    "https://stake.com/_api/graphql",
    headers={
        "x-access-token":TOKEN,
        "Content-Type":"application/json",
        "User-Agent":"Mozilla/5.0",
        "Accept":"application/json"
    },
    json={"query":query}
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:1000]}")
