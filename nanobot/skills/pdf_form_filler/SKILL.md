# PDF Form Filler Skill

Use this skill to fill PDF forms with high reliability using iterative verification.

## When to Use

- Fill Australian government forms (40SP, 47SP, 888, etc.)
- Complete applications requiring accurate data entry
- Any task where accuracy is critical and needs verification

## How to Use

### Option 1: Direct Tool Call

Use the `coach_player` tool directly:

```
Use the coach_player tool to fill the PDF form at /path/to/form.pdf with:
- Sponsor: Sean Alexander Cheong, DOB: 31/10/2003
- Applicant: Xiao Chu, Passport: EJ7925920
- Address: 66 Tangerine Drive, Quakers Hill NSW 2763
```

### Option 2: Via Skill Context

The agent understands PDF form filling when you describe the task naturally.

## Parameters

- `task`: Description of what to fill
- `context`: Additional data (file paths, form fields, etc.)
- `verification_mode`: "llm" (default) or "pdf" for visual verification
- `max_iterations`: Max retry attempts (default: 3)
- `confidence_threshold`: Minimum confidence (default: 0.8)

## Example Data (Partner Visa)

```
Sponsor: Sean Alexander Cheong
- DOB: 31/10/2003
- Born: Campbelltown, Australia
- Citizenship: Australian

Applicant: Xiao Chu  
- DOB: 01/02/2000
- Passport: EJ7925920
- Visa: Student
- Arrived: 05/03/2024

Address: 66 Tangerine Drive, Quakers Hill NSW 2763

Relationship:
- Met: 30/08/2024
- Started dating: 30/08/2024
- Status: De facto
```

## Verification

The Coach-Player pipeline:
1. **Player** executes the task
2. **Coach** verifies the output
3. If confidence < threshold, iterates up to max_iterations
4. Returns final result with confidence score
