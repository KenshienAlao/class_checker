import z from "zod";

const AuthSchema = z.object({
  firstName: z
    .string()
    .min(1, "First name must be at least 1 character")
    .max(32, "First name must be at most 32 characters")
    .trim(),
  lastName: z
    .string()
    .min(1, "Last name must be at least 1 character")
    .max(32, "Last name must be at most 32 characters")
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
  terms: z.boolean().refine((v) => v, "You must agree to the terms"),
});

export const RegisterSchema = AuthSchema.refine(
  (data) => data.password === data.confirm,
  {
    message: "Passwords do not match",
    path: ["confirm"],
  },
);

export const LoginSchema = AuthSchema.omit({
  firstName: true,
  lastName: true,
  confirm: true,
  terms: true,
}).extend({
  password: z.string().min(1, "Password is required"),
});

export type RegisterValidated = z.infer<typeof RegisterSchema>;
export type LoginValidated = z.infer<typeof LoginSchema>;
