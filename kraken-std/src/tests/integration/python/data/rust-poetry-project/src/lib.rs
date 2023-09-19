use pyo3::prelude::*;

#[pymodule]
fn rust_poetry_project(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    #[pyfn(m)]
    fn sum_as_string(a: usize, b: usize) -> String {
        (a + b).to_string()
    }
    Ok(())
}
