# Betting Analysis API

This is a personal betting analysis application designed to store and analyze betting data.

## API Documentation

All endpoints are prefixed with `/user/`.

### 1. Register User
`POST /user/register/`

**Request Body (JSON):**
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "password": "securepassword123"
}
```

**Response (201 Created):**
```json
{
  "message": "User created successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "created_at": "2026-06-18T10:00:00Z",
    "updated_at": "2026-06-18T10:00:00Z"
  }
}
```

### 2. Login
`POST /user/login/`

**Request Body (JSON):**
```json
{
  "username": "johndoe",
  "password": "securepassword123"
}
```

**Response (200 OK):**
```json
{
  "message": "Login successful",
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "created_at": "2026-06-18T10:00:00Z",
    "updated_at": "2026-06-18T10:00:00Z"
  }
}
```

### 3. User Profile
`GET /user/profile/<uuid:pk>/`
*Requires authentication via Bearer token.*

**Response (200 OK):**
```json
{
  "message": "User profile retrieved successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "created_at": "2026-06-18T10:00:00Z",
    "updated_at": "2026-06-18T10:00:00Z"
  }
}
```

### 4. Create Bet
`POST /user/create/`
*Requires authentication via Bearer token.*

**Request Body (JSON):**
```json
{
  "stake": "500.00",
  "potential_payout": "750.00",
  "game_type": "Football",
  "number_of_games": "3"
}
```

**Response (201 Created):**
```json
{
  "message": "Bet created successfully",
  "data": {
    "id": 1,
    "bet_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "stake": "500.00",
    "potential_payout": "750.00",
    "game_type": "Football",
    "number_of_games": "3",
    "created_at": "2026-06-22T14:30:00Z",
    "result": "pending"
  }
}
```

### 5. List All Bets
`GET /user/view-bets/`
*Requires authentication via Bearer token.*

**Response (200 OK):**
```json
{
  "message": "Bet details retrieved successfully",
  "data": [
    {
      "id": 1,
      "bet_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "stake": "500.00",
      "potential_payout": "750.00",
      "game_type": "Football",
      "number_of_games": "3",
      "result": "won"
    },
    {
      "id": 2,
      "bet_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "stake": "200.00",
      "potential_payout": "0.00",
      "game_type": "Basketball",
      "number_of_games": "2",
      "result": "lost"
    }
  ]
}
```

### 6. Get Individual Bet
`GET /user/view-bets/<uuid:bet_id>/`
*Requires authentication via Bearer token.*

**Response (200 OK):**
```json
{
  "message": "Bet details retrieved successfully",
  "data": {
    "id": 1,
    "bet_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "stake": "500.00",
    "potential_payout": "750.00",
    "game_type": "Football",
    "number_of_games": "3",
    "result": "won"
  }
}
```

### 7. Rollover Calculator
`POST /user/rollover/`
*Requires authentication via Bearer token.*

**Request Body (JSON):**
```json
{
  "stake": "500.00",
  "payout": "750.00",
  "days": "30"
}
```

**Response (200 OK):**
```json
{
  "message": "Rollover requirement calculated successfully",
  "data": {
    "stake": 500.0,
    "payout": 750.0,
    "rollover_requirement": 0.5,
    "daily_rollover": 1.01
  }
}
```
