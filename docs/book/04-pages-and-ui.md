# 4. Pages and UI

## Apps and pages
An app sets the entry page:
```ai
app "my-app":
  entry_page "home"
```

Page structure:
```ai
page "home" at "/":
  heading "Welcome"
  text "This is the homepage."
  section "cta":
    heading "Get started"
    text "Fill the form below."
```

## Layout elements
- `section`, `heading`, `text`, `image`
- `use form "Signup Form"` to embed forms defined elsewhere

## Inputs, buttons, navigation, and state
```ai
page is "signup" at "/signup":
  state name is ""
  input is "Your name" as name

  button is "Submit":
    on click:
      do flow is "register_user" with name: name
```

### Input validation
Declare simple validation rules on inputs and textareas. Validation runs before flows execute; if validation fails, errors are returned and shown in Studio preview.

```ai
page is "register" at "/register":
  section is "form":
    input is "email":
      bind is state.email
      required is true
      min_length is 5
      max_length is 200
      pattern is ".+@.+\\..+"
      message is "Please enter a valid email address."

    textarea is "bio":
      bind is state.bio
      max_length is 500
      message is "Bio must be at most 500 characters."
```

Fields:
- `required` (bool)
- `min_length` / `max_length` (ints)
- `pattern` (regex string)
- `message` (custom error)

### Navigation via buttons

By path:
```ai
page is "home" at "/":
  section is "main":
    button is "Go to Chat":
      on click:
        navigate to "/chat"

page is "chat" at "/chat":
  section is "main":
    text is "Welcome to chat!"
```

By page name:
```ai
button is "Go to Chat":
  on click:
    navigate to page "chat"
```

Legacy forms without `is` are also valid:
```ai
button "Go":
  on click:
    navigate "/chat"
```

Navigation works in both the runtime and the Studio preview: clicking the button switches the current page to the target path or page.

## Expanded UI components
English-style components for richer layouts:
```ai
page is "chat" at "/chat":
  section is "main":
    card is "conversation":
      row:
        text is "User:"
        badge is "Premium"
      textarea is "question":
        bind is question
      row:
        button is "Ask":
          on click:
            do flow is "answer_with_rag"
```

- `card` — bordered container, can wrap any children.
- `row` / `column` — flex stacks for horizontal/vertical layout.
- `textarea` — multi-line input (use `bind` to connect to state).
- `badge` — small pill/label for inline status.

Legacy forms without `is` still parse, but the English surface is preferred.

## Chat / Message Components
```ai
page is "chat" at "/chat":
  section is "main":
    card is "conversation":
      message_list:
        message:
          role is "user"
          text is state.question
        message:
          role is "assistant"
          text is state.answer
```
- `message_list` renders a vertical list of chat bubbles.
- `message` supports `role` (`user`, `assistant`, or custom) and `text` expressions (state, step output, or literals).
- Both classic and `is` syntaxes are accepted; prefer the English style for clarity.

## Conditionals in UI
```ai
when name is not "":
  show:
    text "Hello, " + name
otherwise:
  show:
    text "Enter your name."
```

## Components and styling
- Components: `component "PrimaryButton": ... render: ...`
- Styling: `color is primary`, `background color is "#000"`, `layout is row`, `padding is medium`, `align is center`.

## Studio workflow
- Open Studio (`n3 studio`) and navigate to `/studio`.
- Use Inspector Mode to inspect elements; Preview Mode to interact.
- Lint shows soft warnings; diagnostics show errors.

## Exercises
1. Build a page with a hero section and a call-to-action button that calls a flow.
2. Add a conditional block that shows a thank-you message after a boolean state is true.
3. Create a simple component for a secondary button and use it twice.
