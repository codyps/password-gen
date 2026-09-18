# apple-password-gen

Generate secure passwords following the default format in
[Apple's public reference generator](https://developer.apple.com/password-rules/):
three six-character groups separated by hyphens, with one digit and one uppercase
letter. Digit-leading groups preserve the `digit + CVC + CV` syllable pattern;
uppercase `O` and both forms of `L` are excluded, while lowercase `o` is allowed.

Apple's on-device offensive-word filtering and site-specific password rules are
not implemented.

## Usage (CLI)

```bash
cargo install apple-password-gen
```

Then run:

```bash
apple-password-gen
```

# Usage (Library)

In addition to the cmdline tool, you can also use the library in your own projects.

```
cargo add apple-password-gen
```

Then in your code:

```rust
fn main() {
    let password = apple_password_gen::generate();
    println!("{}", password);
}
```
