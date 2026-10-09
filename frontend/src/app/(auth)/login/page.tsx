"use client";

import { FormEvent } from "react";

export default function Login() {
  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const formData = new FormData(e.currentTarget);

    const validateData = console.log(formData);
  };

  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="flex flex-col justify-center items-center gap-2">
        <h1>Login</h1>
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="flex gap-2">
            <label htmlFor="email">Email</label>
            <input
              className="border border-gray-300 rounded-md"
              type="email"
              id="email"
              name="email"
            />
          </div>
          <div className="flex gap-2">
            <label htmlFor="password">Password</label>
            <input
              className="border border-gray-300 rounded-md"
              type="password"
              id="password"
              name="password"
            />
          </div>
          <button
            className="bg-blue-500 text-white rounded-md p-2"
            type="submit"
          >
            Login
          </button>
        </form>
      </div>
    </div>
  );
}
