//steps
1. The user uploads an image or a text or a text with content from a textbook.
2. read the text and identify key topics to be understood
3. read the //rules below
4. generate {fill the blanks texts} with at least 6 sentences or 70-100 words.
5. STRICTLY follow the guidelines '//rules' and '//JSON Output' for formatting the output.


//rules
- IMPORTANT: the custom texts by "text" are full with no blanks
- IMPORTANT: between each blank there are at least 5 words
- IMPORTANT: Each custom text has at least 6 sentences
- IMPORTANT: Each text has 5 "blanks" and 5 "wrong_substitute"
- IMPORTANT: generate for each identified blank one plausible wrong_substitute according to //JSON Output.
- IMPORTANT: the blanks and wrong_substitutes are unique
- IMPORTANT: you generate just the JSON-Format

//JSON Output
[
  {
    "text": "{fill the blanks text 1}",
    "blanks": ["blank1", "blank2", "blank3", "blank4", "blank5"],
    "wrong_substitutes": [
      "wrong substitute blank1",
      "wrong substitute blank2",
      "wrong substitute blank3",
      "wrong substitute blank4",
      "wrong substitute blank5"
    ]
  },
  {
    "text": "{fill the blanks text 2}",
    "blanks": ["blank1", "blank2", "blank3", "blank4", "blank5"],
    "wrong_substitutes": [
      "wrong substitute blank1",
      "wrong substitute blank2",
      "wrong substitute blank3",
      "wrong substitute blank4",
      "wrong substitute blank5"
    ]
  },
  {
    "text": "{fill the blanks text 3}",
    "blanks": ["blank1", "blank2", "blank3", "blank4", "blank5"],
    "wrong_substitutes": [
      "wrong substitute blank1",
      "wrong substitute blank2",
      "wrong substitute blank3",
      "wrong substitute blank4",
      "wrong substitute blank5"
    ]
  },
  {
    "text": "{fill the blanks text 4}",
    "blanks": ["blank1", "blank2", "blank3", "blank4", "blank5"],
    "wrong_substitutes": [
      "wrong substitute blank1",
      "wrong substitute blank2",
      "wrong substitute blank3",
      "wrong substitute blank4",
      "wrong substitute blank5"
    ]
  }
]

single question Example Output :
```json
[
  {
    "text": "Switzerland's direct democracy empowers citizens to participate in decision-making through referendums and initiatives. A referendum allows citizens to challenge laws passed by the parliament, requiring 50,000 signatures within 100 days to trigger a national vote. Conversely, a popular initiative enables citizens to propose constitutional amendments, needing 100,000 signatures within 18 months.",
    "blanks": ["challenge laws", "50,000 signatures", "100 days", "100,000 signatures", "18 months"],
    "wrong_substitutes": [
      "change laws",
      "10,000 signatures",
      "1000 days",
      "200,000 signatures",
      "12 months"
    ]
  }
]
```
