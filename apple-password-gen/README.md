# apple-password-gen

Generate secure passwords using the same format used by apple passwords.

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
