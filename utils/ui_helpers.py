import streamlit as st

# Makes every input box white with a dark-blue border on every device,
# even when the phone or browser is in dark mode.
FORCE_LIGHT_INPUTS_SCRIPT = """
<script>
(() => {
    // st.html() is rendered in the app document (not a separate iframe).
    const appDocument = document;

    let colorSchemeMeta = appDocument.querySelector('meta[name="color-scheme"]');
    if (!colorSchemeMeta) {
        colorSchemeMeta = appDocument.createElement('meta');
        colorSchemeMeta.name = 'color-scheme';
        appDocument.head.appendChild(colorSchemeMeta);
    }
    colorSchemeMeta.content = 'only light';

    function enforceLightInputs() {
        const inputWrappers = appDocument.querySelectorAll('[data-baseweb="input"]');
        inputWrappers.forEach((inputWrapper) => {
            inputWrapper.style.setProperty('background-color', '#FFFFFF', 'important');
            inputWrapper.style.setProperty('background', '#FFFFFF', 'important');
            inputWrapper.style.setProperty('border', '2px solid #030391', 'important');
            inputWrapper.style.setProperty('border-radius', '14px', 'important');
            inputWrapper.style.setProperty('box-shadow', 'none', 'important');
        });

        const innerDivs = appDocument.querySelectorAll(
            '[data-baseweb="base-input"], [data-baseweb="input"] > div'
        );
        innerDivs.forEach((innerDiv) => {
            innerDiv.style.setProperty('background-color', '#FFFFFF', 'important');
            innerDiv.style.setProperty('background', '#FFFFFF', 'important');
            innerDiv.style.setProperty('border', 'none', 'important');
        });

        appDocument.querySelectorAll('input').forEach((inputElement) => {
            inputElement.style.setProperty('background-color', '#FFFFFF', 'important');
            inputElement.style.setProperty('background', '#FFFFFF', 'important');
            inputElement.style.setProperty('color', '#000000', 'important');
            inputElement.style.setProperty('-webkit-text-fill-color', '#000000', 'important');
        });
    }

    enforceLightInputs();

    // Streamlit reruns can add new input elements after this script executes.
    if (!window.__forceLightInputsObserver) {
        window.__forceLightInputsObserver = new MutationObserver(enforceLightInputs);
        window.__forceLightInputsObserver.observe(appDocument.body, {
            childList: true,
            subtree: true
        });
    }
})();
</script>
"""


def force_light_inputs() -> None:
    """Apply the light input styling without using the deprecated components API."""
    st.html(FORCE_LIGHT_INPUTS_SCRIPT, unsafe_allow_javascript=True)
