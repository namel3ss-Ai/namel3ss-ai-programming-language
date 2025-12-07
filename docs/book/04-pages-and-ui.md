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

## Inputs, buttons, and state
```ai
page "signup" at "/signup":
  state name is ""
  input "Your name" as name

  button "Submit":
    on click:
      do flow "register_user" with name: name
```

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
