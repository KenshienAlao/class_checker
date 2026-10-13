import z from "zod";

const AuthSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(64, "Name must be at most 64 characters")
    .trim(),
  email: z
    .email("Email must be valid")
    .min(1, "Email is required")
    .max(254, "Email must be at most 254 characters")
    .trim(),
  password: z
    .string()
    .min(1, "Password is required")
    .min(8, "Password must be at least 8 characters")
    .max(128, "Password must be at most 128 characters")
    .regex(/[a-z]/, "Password must contain at least one lowercase letter")
    .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
    .regex(/[0-9]/, "Password must contain at least one number")
    .regex(
      /[^a-zA-Z0-9]/,
      "Password must contain at least one special character",
    ),
  confirm: z.string().min(1, "Password confirmation is required"),
});

export const SignupSchema = AuthSchema.refine(
  (data) => data.password === data.confirm,
  {
    message: "Passwords do not match",
    path: ["confirm"],
  },
);

export const SigninSchema = AuthSchema.omit({
  name: true,
  confirm: true,
}).extend({
  password: z.string().min(1, "Password is required"),
});

export type SignupValidated = z.infer<typeof SignupSchema>;
export type SigninValidated = z.infer<typeof SigninSchema>;
