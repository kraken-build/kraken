#[cfg(feature = "a")]
struct T {}

#[cfg(all(feature = "a", feature = "c", not(feature = "b")))]
struct T {
    field: String,
}

fn main() {
    #[cfg(feature = "a")]
    let _value: T = T {};
}
