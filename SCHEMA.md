# API Schema

## 1. Register User
`POST /user/register/`

### Request Body
| Field      | Type   | Required | Constraints                       |
|------------|--------|----------|-----------------------------------|
| username   | string | Yes      | Max 30 chars, unique              |
| email      | email  | Yes      | Valid email format, unique        |
| first_name | string | Yes      | Max 30 chars                      |
| last_name  | string | Yes      | Max 30 chars                      |
| password   | string | Yes      | Write-only, not returned          |

### Response (201 Created)
| Field        | Type   | Description                    |
|--------------|--------|--------------------------------|
| message      | string | Success confirmation           |
| data.id      | uuid   | Auto-generated UUID (RO)       |
| data.email   | string | User email                     |
| data.first_name | string | User first name              |
| data.last_name  | string | User last name               |
| data.username   | string | Username                     |
| data.created_at | datetime | Auto set on creation (RO)  |
| data.updated_at | datetime | Auto updated on save (RO)   |

---

## 2. Login
`POST /user/login/`

### Request Body
| Field    | Type   | Required | Constraints |
|----------|--------|----------|-------------|
| username | string | Yes      | Must exist  |
| password | string | Yes      | Must match  |

### Response (200 OK)
| Field         | Type   | Description                |
|---------------|--------|----------------------------|
| message       | string | Success confirmation       |
| access        | string | JWT access token           |
| refresh       | string | JWT refresh token          |
| data          | object | Same as Register response  |

---

## 3. User Profile
`GET /user/profile/<uuid:pk>/`

### URL Parameter
| Parameter | Type | Required | Description               |
|-----------|------|----------|---------------------------|
| pk        | uuid | Yes      | User's UUID primary key   |

### Headers
| Key           | Value                          |
|---------------|--------------------------------|
| Authorization | Bearer `<access_token>`        |

### Response (200 OK)
| Field         | Type   | Description                          |
|---------------|--------|--------------------------------------|
| message       | string | Success confirmation                 |
| data          | object | Same as Register response            |

---

## 4. Create Bet
`POST /user/create/`

### Headers
| Key           | Value                          |
|---------------|--------------------------------|
| Authorization | Bearer `<access_token>`        |

### Request Body
| Field           | Type   | Required | Constraints                       |
|-----------------|--------|----------|-----------------------------------|
| stake           | number | Yes      | Decimal(10,2), min 100            |
| potential_payout| number | No       | Decimal(10,2), nullable           |
| game_type       | string | Yes      | Max 50 chars                      |
| number_of_games | string | No       | Max 3 chars, nullable             |

### Response (201 Created)
| Field                     | Type     | Description                      |
|---------------------------|----------|----------------------------------|
| message                   | string   | Success confirmation             |
| data.id                   | integer  | Auto-increment ID (RO)           |
| data.bet_id               | uuid     | Auto-generated UUID (RO)         |
| data.stake                | decimal  | Bet stake amount                 |
| data.potential_payout     | decimal  | Potential payout, nullable       |
| data.game_type            | string   | Type of game                     |
| data.number_of_games      | string   | Number of games, nullable        |
| data.created_at           | datetime | Auto set on creation (RO)        |
| data.result               | string   | Default: "pending" (RO)          |

### Validation Errors (400)
- `stake`: "Stake cannot be less than 100NGN."

---

## 5. List All Bets
`GET /user/view-bets/`

### Headers
| Key           | Value                          |
|---------------|--------------------------------|
| Authorization | Bearer `<access_token>`        |

### Response (200 OK)
Returns array of bet objects:

| Field                   | Type     | Description                      |
|-------------------------|----------|----------------------------------|
| message                 | string   | Success confirmation             |
| data[].id               | integer  | Auto-increment ID (RO)           |
| data[].bet_id           | uuid     | Auto-generated UUID (RO)         |
| data[].stake            | decimal  | Bet stake amount                 |
| data[].potential_payout | decimal  | Potential payout, nullable       |
| data[].game_type        | string   | Type of game                     |
| data[].number_of_games  | string   | Number of games, nullable        |
| data[].result           | string   | "pending", "won", or "lost"      |
| data[].profit_loss      | string/decimal | Calculated: "Bet is Pending", positive decimal (won), or negative decimal (lost) |

---

## 6. Get Individual Bet
`GET /user/view-bets/<uuid:bet_id>/`

### URL Parameter
| Parameter | Type | Required | Description               |
|-----------|------|----------|---------------------------|
| bet_id    | uuid | Yes      | Bet's UUID identifier     |

### Headers
| Key           | Value                          |
|---------------|--------------------------------|
| Authorization | Bearer `<access_token>`        |

### Response (200 OK)
| Field              | Type     | Description                      |
|--------------------|----------|----------------------------------|
| message            | string   | Success confirmation             |
| data               | object   | Same single bet object as above  |

---

## 7. Rollover Calculator
`POST /user/rollover/`

### Headers
| Key           | Value                          |
|---------------|--------------------------------|
| Authorization | Bearer `<access_token>`        |

### Request Body
| Field  | Type   | Required | Constraints                |
|--------|--------|----------|----------------------------|
| stake  | number | Yes      | Must be > 0                |
| payout | number | Yes      | Must be > 0                |
| days   | number | Yes      | Positive integer           |

### Response (200 OK)
| Field                        | Type   | Description                              |
|------------------------------|--------|------------------------------------------|
| message                      | string | Success confirmation                     |
| data.stake                   | float  | Input stake amount                       |
| data.payout                  | float  | Input payout amount                      |
| data.rollover_requirement    | float  | (payout - stake) / stake                 |
| data.daily_rollover          | float  | rollover_requirement ^ (1/days), rounded |

### Validation Errors (400)
- Missing field: `"<field> is required."`
- Non-numeric value: `"Stake and payout must be numbers."`
- Non-positive value: `"Stake and payout must be greater than zero."`
