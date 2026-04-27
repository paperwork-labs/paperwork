import React from 'react';
import { cn } from '@/lib/utils';

import { Input } from './input';
import { Textarea } from './textarea';

type Props = React.ComponentProps<'div'> & {
  label: string;
  helperText?: string;
  errorText?: string;
  children: React.ReactNode;
  required?: boolean;
  /** When children wrap the control (e.g. password + toggle), set this to match the input `id`. */
  htmlFor?: string;
};

export default function FormField({
  label,
  helperText,
  errorText,
  children,
  className,
  required,
  htmlFor: htmlForProp,
  ...props
}: Props) {
  const generatedId = React.useId();
  const invalid = Boolean(errorText);

  let labelHtmlFor: string | undefined = htmlForProp;
  let renderedChildren = children;

  if (!labelHtmlFor && React.Children.count(children) === 1) {
    try {
      const only = React.Children.only(children);
      if (React.isValidElement(only)) {
        const el = only as React.ReactElement<{ id?: string }>;
        if (el.type === Input || el.type === Textarea) {
          const existingId = el.props.id;
          labelHtmlFor = existingId ?? generatedId;
          if (!existingId) {
            renderedChildren = React.cloneElement(el, { id: generatedId });
          }
        }
      }
    } catch {
      // Multiple children hidden inside a single fragment edge case; skip auto-link
    }
  }

  return (
    <div
      data-invalid={invalid ? '' : undefined}
      className={cn('grid gap-2', className)}
      {...props}
    >
      <label
        htmlFor={labelHtmlFor}
        className="text-sm font-medium text-muted-foreground"
      >
        {label}
        {required ? <span className="text-destructive"> *</span> : null}
      </label>
      {renderedChildren}
      {helperText ? <p className="text-xs text-muted-foreground/90">{helperText}</p> : null}
      {errorText ? <p className="text-xs font-medium text-destructive">{errorText}</p> : null}
    </div>
  );
}
