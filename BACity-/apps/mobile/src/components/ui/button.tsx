"use client";

import { createButton } from "@gluestack-ui/core/button/creator";
import { UIIcon } from "@gluestack-ui/core/icon/creator";
import {
  tva,
  useStyleContext,
  withStyleContext,
  type VariantProps,
} from "@gluestack-ui/utils/nativewind-utils";
import { withUniwind } from "uniwind";
import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

const SCOPE = "BUTTON";
const Root = withStyleContext(Pressable, SCOPE);
const StyledUIIcon = withUniwind(UIIcon);

const UIButton = createButton({
  Root,
  Text,
  Group: View,
  Spinner: ActivityIndicator,
  Icon: StyledUIIcon,
});

const buttonStyle = tva({
  base: "flex-row items-center justify-center gap-2 rounded-2xl data-[disabled=true]:opacity-50",
  variants: {
    variant: {
      solid: "bg-primary data-[hover=true]:bg-primary/90 data-[active=true]:bg-primary/90",
      dark: "bg-foreground data-[hover=true]:bg-foreground/90 data-[active=true]:bg-foreground/90",
      outline: "border border-border bg-card data-[hover=true]:bg-secondary",
      ghost: "bg-transparent data-[hover=true]:bg-secondary",
    },
    size: {
      sm: "min-h-10 px-4",
      md: "min-h-12 px-5",
      lg: "min-h-14 px-6",
    },
  },
});

const buttonTextStyle = tva({
  base: "font-semibold",
  parentVariants: {
    variant: {
      solid: "text-primary-foreground",
      dark: "text-white",
      outline: "text-foreground",
      ghost: "text-primary",
    },
    size: {
      sm: "text-xs",
      md: "text-sm",
      lg: "text-base",
    },
  },
});

const buttonSpinnerStyle = tva({ base: "" });
const buttonIconStyle = tva({ base: "fill-none pointer-events-none shrink-0" });

type IButtonProps = Omit<
  React.ComponentPropsWithoutRef<typeof UIButton>,
  "context"
> &
  VariantProps<typeof buttonStyle> & { className?: string };

const Button = React.forwardRef<React.ElementRef<typeof UIButton>, IButtonProps>(
  ({ className, variant = "solid", size = "md", ...props }, ref) => (
    <UIButton
      ref={ref}
      {...props}
      className={buttonStyle({ variant, size, class: className })}
      context={{ variant, size }}
    />
  )
);

type IButtonTextProps = React.ComponentPropsWithoutRef<typeof UIButton.Text> &
  VariantProps<typeof buttonTextStyle> & { className?: string };

const ButtonText = React.forwardRef<
  React.ElementRef<typeof UIButton.Text>,
  IButtonTextProps
>(({ className, size, ...props }, ref) => {
  const { size: parentSize, variant: parentVariant } = useStyleContext(SCOPE);
  return (
    <UIButton.Text
      ref={ref}
      {...props}
      className={buttonTextStyle({
        parentVariants: { size: parentSize, variant: parentVariant },
        size,
        class: className,
      })}
    />
  );
});

const ButtonSpinner = React.forwardRef<
  React.ElementRef<typeof UIButton.Spinner>,
  React.ComponentPropsWithoutRef<typeof UIButton.Spinner>
>(({ className, ...props }, ref) => (
  <UIButton.Spinner
    ref={ref}
    {...props}
    className={buttonSpinnerStyle({ class: className })}
  />
));

type IButtonIcon = React.ComponentPropsWithoutRef<typeof UIButton.Icon> &
  VariantProps<typeof buttonIconStyle> & {
    className?: string;
    as?: React.ElementType;
    height?: number;
    width?: number;
  };

const ButtonIcon = React.forwardRef<
  React.ElementRef<typeof UIButton.Icon>,
  IButtonIcon
>(({ className, ...props }, ref) => (
  <UIButton.Icon
    ref={ref}
    {...props}
    className={buttonIconStyle({ class: className })}
  />
));

Button.displayName = "Button";
ButtonText.displayName = "ButtonText";
ButtonSpinner.displayName = "ButtonSpinner";
ButtonIcon.displayName = "ButtonIcon";

export { Button, ButtonIcon, ButtonSpinner, ButtonText };
