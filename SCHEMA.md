# Database Schema
## Settings
- id (PK): Integer
- min_refresh_interval: Float (Default: 20.0)
- max_refresh_interval: Float (Default: 30.0)

## Users
- id (PK): Integer
- name: String
- webhook_url: String (Discord webhook URL for notifications)
- stop_time: DateTime (Nullable, time when user tracking should stop)

## Courses
- id (PK): Integer
- course_name: String
- professor: String
- crn: String (Unique)
- last_seat_count: Integer (Nullable, for tracking seat changes)
- last_updated: DateTime (When seat count was last updated)

## user_courses (Junction Table)
- user_id (PK, FK): Integer (References users.id)
- course_id (PK, FK): Integer (References courses.id)

## NotificationHistory
- id (PK): Integer
- user_id (FK): Integer (References users.id)
- course_id (FK): Integer (References courses.id)
- seat_count: Integer (Seat count at time of notification)
- notification_time: DateTime (When notification was sent)
- notification_type: String (initial, change, or full)
