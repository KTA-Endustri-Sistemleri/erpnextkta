export function applyDecimalInputMode(fields: any[]) {
    fields.forEach(f => {
        if (["Float", "Currency", "Percent"].includes(f.fieldtype)) {
            f.on_make = (field: any) => {
                if (field.$input) {
                    field.$input.attr("inputmode", "decimal");
                }
            };
        }
    });
    return fields;
}
