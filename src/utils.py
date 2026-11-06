from uuid import uuid4


def generate_account_number():
    return uuid4().hex[:8].upper()

def build_account_table(rows):
    label_width = 20   
    value_width = 20
    
    sep = "-" * (label_width + value_width + 3)  # +3 на " | "
    
    lines = [sep]
    for label, value in rows[:-1]:
        lines.append(f"{label:<{label_width}} | {value:>{value_width}}")
    lines.append(sep)
    lines.append(f"{rows[-1][0]:<{label_width}} | {rows[-1][1]:>{value_width}}")
    return "\n".join(lines)+"\n"